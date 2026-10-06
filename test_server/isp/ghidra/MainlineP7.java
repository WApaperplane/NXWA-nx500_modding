// p7 主干分析：MMU 页表解算 + 从 Reset 顺启动链 + 批量导出全量伪代码
// 方法要点（吸取教训：抓主干映射关系，不追符号名/键名等细枝末节）
//   1) Reset 建的是 1:1 页表 => 运行时虚拟地址可直接换算成 file 偏移
//   2) 从 Reset 的间接跳转目标出发，BSF 整条启动链
//   3) 一次性导出全部函数伪代码，供外部 grep
//@category NX-KS2
//@author NX-KS2

import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.data.*;
import java.io.*;
import java.util.*;

public class MainlineP7 extends GhidraScript {

    private File dir;
    private DecompInterface di;
    private Map<String, String> cache = new HashMap<>();

    // Reset 反编译里读出的常量
    private static final long RAM_LO   = 0x80000000L;
    private static final long RAM_HI   = 0x81000000L;
    private static final long PTE_BASE = 0x81002000L;   // DAT_00000244
    private static final long PTE_FLAG = 0x1c0eL;       // DAT_00000248
    private static final long DAT_240  = 0x402L;        // 循环1 用的标志
    private static final long INDIR    = 0x80000e38L;   // DAT_0000025c 低32位

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        dir = new File(args.length > 0 ? args[0] : ".");
        dir.mkdirs();
        di = new DecompInterface();
        di.openProgram(currentProgram);

        a_pageTable();
        b_bootChain();
        c_dumpAllPseudocode();

        di.dispose();
        println("MainlineP7 done.");
    }

    // ==============================================================
    // 1. 页表完整解算：虚拟地址 -> file 偏移
    // ==============================================================
    private void a_pageTable() throws Exception {
        PrintWriter p = pw("50_page_table.txt");
        p.println("=== 1: Reset 建立的页表完整解算 ===");
        p.println("结论前提：p7 用 1:1 映射 ⇒ 虚拟地址 X (0x80000000-0x80ffffff) 的");
        p.println("          file 偏移 = X - 0x80000000");
        p.println();

        // 循环2 写的 16 个 PTE: *0x81002000+i*4 = 0x80000000 + i*0x100000 | 0x1c0e
        p.println("--- 16 个 PTE（循环2 写入，虚拟 0x80000000-0x80ffffff）---");
        p.printf("  %-6s %-12s %-12s %-10s %s%n", "idx", "VA", "PTE值", "→PA", "flags");
        for (int i = 0; i < 16; i++) {
            long va = RAM_LO + i * 0x100000L;
            long pte = va | PTE_FLAG;
            long pa = pte & 0xFFFFF000L;
            p.printf("  [%2d]  0x%08x  0x%08x  0x%08x  0x%x%n", i, va, pte, pa, pte & 0xFFF);
        }

        // 循环1 写的项: *0x81000000 + i*4 = i*0x100000 | 0x402  (i 从 0 到 ?)
        p.println();
        p.println("--- 循环1 写入的项（*0x81000000 起，值 = i*0x100000 | 0x402）---");
        int n1 = 0;
        for (long i = 0; i < 0x100000L; i += 0x100000L) { n1++; if (n1 > 4096) break; }
        p.println("  uVar4 从 0 步进 0x100000 到 4096 溢出 => 写 " + n1 + " 项(覆盖 4GB)");
        p.println("  实际语义: 为 0x00000000-0xFFFFFFFF 全部 4GB 建页表? 需看完整反编译确认循环条件");

        // 关键换算
        p.println();
        p.println("--- 关键换算 ---");
        p.printf("  DAT_0000025c = 0x80000e38 (虚拟地址)%n");
        long fileOff = INDIR - RAM_LO;
        p.printf("  ⇒ file 偏移 = 0x80000e38 - 0x80000000 = 0x%x (%d)%n", fileOff, fileOff);
        Function f = getFunctionAt(toAddr(fileOff));
        p.printf("  该地址的函数: %s%n", f == null ? "(无函数, 需手动建)" : f.getName());
        if (f != null) {
            p.printf("  大小 = %d 字节, 结束 @ 0x%x%n", f.getBody().getNumAddresses(),
                    f.getBody().getMaxAddress().getOffset());
        }

        // 验证：Ghidra 反编译时的 warning "Could not follow disassembly flow into
        // non-existing memory at 800027e0" 说明 0x8000xxxx 段被当代码访问但不在镜像内
        p.println();
        p.println("--- 独立验证：Ghidra 报的越界访问地址 ---");
        p.println("  Decompiler warning 里出现过 800027e0 / 80005040 / 80006000 等");
        p.printf("  0x800027e0 - 0x80000000 = 0x%x  (若该处有代码则换算成立)%n", 0x800027e0L - RAM_LO);

        // 把换算表写进文件供后续脚本用
        PrintWriter m = pw("50_virt2file.txt");
        m.println("# 虚拟地址 -> file 偏移 换算表 (1:1 映射, 1MB 粒度)");
        m.println("# 虚拟区间 0x80000000-0x81000000 共 16 段");
        for (int i = 0; i < 16; i++) {
            long va = RAM_LO + i * 0x100000L;
            m.printf("0x%08x 0x%08x%n", va, va - RAM_LO);
        }
        m.close();
        p.close();
    }

    // ==============================================================
    // 2. 启动链 BFS：从 Reset 的间接跳转目标开始
    // ==============================================================
    private void b_bootChain() throws Exception {
        PrintWriter p = pw("51_boot_chain.txt");
        p.println("=== 2: 从 Reset 出发的启动链（BFS，含跨段虚拟地址换算）===");

        long start = INDIR - RAM_LO;     // 0xe38
        p.println("起点 = file 0x" + Long.toHexString(start) + " (虚拟 0x" + Long.toHexString(INDIR) + ")");
        p.println();

        Set<String> visited = new HashSet<>();
        List<long[]> queue = new ArrayList<>();
        queue.add(new long[]{start, 0});
        visited.add(String.valueOf(start));

        int maxDepth = 3;
        int printed = 0;
        while (!queue.isEmpty()) {
            long[] cur = queue.remove(0);
            long off = cur[0];
            int depth = (int) cur[1];
            if (depth > maxDepth || printed > 120) break;

            Function f = getFunctionAt(toAddr(off));
            String label = f == null ? "(no func @" + Long.toHexString(off) + ")" : f.getName();
            p.printf("%n%s--- [d%d] file 0x%x  %s  size=%d ---%n",
                    "  ".repeat(depth), depth, off, label,
                    f == null ? 0 : f.getBody().getNumAddresses());

            if (f != null) {
                String c = decomp(f);
                if (c != null) {
                    String show = c.length() > 2500 ? c.substring(0, 2500) + "\n  ...[truncated]" : c;
                    for (String line : show.split("\n")) p.println("    " + line);
                }
                // 收集被调用者
                if (depth < maxDepth) {
                    for (Address a : calledTargets(f)) {
                        long t = a.getOffset();
                        String key = String.valueOf(t);
                        if (visited.contains(key)) continue;
                        visited.add(key);
                        queue.add(new long[]{t, depth + 1});
                    }
                }
            }
            printed++;
        }
        p.println();
        p.println("=== 队列耗尽，统计 ===");
        p.println("访问函数数 = " + visited.size());
        p.close();
    }

    // 收集一个函数里所有 call 目标（把虚拟地址换算成 file 偏移）
    private List<Address> calledTargets(Function f) {
        List<Address> out = new ArrayList<>();
        Set<String> seen = new HashSet<>();
        for (Instruction ins : currentProgram.getListing().getInstructions(f.getBody(), true)) {
            if (!ins.getFlowType().isCall()) continue;
            for (Address a : ins.getFlows()) {
                long t = a.getOffset();
                // 虚拟地址换算
                if (t >= RAM_LO && t < RAM_HI) t -= RAM_LO;
                if (t > currentProgram.getMaxAddress().getOffset()) continue;
                if (seen.add(String.valueOf(t))) out.add(toAddr(t));
            }
        }
        return out;
    }

    // ==============================================================
    // 3. 批量导出全量伪代码（供外部 grep）
    // ==============================================================
    private void c_dumpAllPseudocode() throws Exception {
        PrintWriter idx = pw("52_pseudocode_index.txt");
        PrintWriter all = pw("53_all_pseudocode.c");
        idx.println("=== 全量伪代码索引 ===");
        idx.println("addr\tsize\tname\tout_file\tout_line");
        all.println("// p7 全量伪代码 (Ghidra 12.1.4, ARM:LE:32:v7 base 0x0)");
        all.println("// 用法: grep -n '关键词' 53_all_pseudocode.c");
        all.println();

        FunctionIterator fi = currentProgram.getFunctionManager().getFunctions(true);
        int n = 0, ok = 0, line = 0;
        while (fi.hasNext()) {
            Function f = fi.next();
            if (f.isExternal()) continue;
            n++;
            String c = decomp(f);
            if (c == null) continue;
            ok++;
            idx.printf("0x%x\t%d\t%s\t53_all_pseudocode.c\t%d%n",
                    f.getEntryPoint().getOffset(), f.getBody().getNumAddresses(), f.getName(), line);
            all.printf("// ==== %s @ 0x%x size=%d ====%n", f.getName(),
                    f.getEntryPoint().getOffset(), f.getBody().getNumAddresses());
            all.println(c);
            all.println();
            line++;
            if (n % 2000 == 0) println("  decompiled " + n + "...");
        }
        idx.println();
        idx.println("total functions = " + n);
        idx.println("decompiled ok   = " + ok);
        all.close();
        idx.close();
        println("pseudocode dumped: " + ok + "/" + n);
    }

    // ---- utils ----
    private String decomp(Function f) {
        String key = f.getEntryPoint().toString();
        if (cache.containsKey(key)) return cache.get(key);
        String r = null;
        try {
            DecompileResults res = di.decompileFunction(f, 30, monitor);
            if (res != null && res.decompileCompleted()) r = res.getDecompiledFunction().getC();
        } catch (Exception e) { r = null; }
        cache.put(key, r);
        return r;
    }

    private PrintWriter pw(String n) throws Exception {
        return new PrintWriter(new FileWriter(new File(dir, n), false));
    }
}
