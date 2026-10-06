// P7 深度逆向：三条线并行
//  1) MMU 页表定位 —— 算运行时地址空间（最有价值的新线索）
//  2) vtable → 构造函数 → 类实例（找 CIpcGamma / CMaterial 等）
//  3) 按变量名/子串在伪代码里搜 gamma / color / PostProcess
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
import java.util.regex.*;

public class DeepP7 extends GhidraScript {

    private File dir;
    private DecompInterface di;
    private Map<String, String> decompCache = new HashMap<>();

    private static final int RAM_LO = 0x80000000;
    private static final int RAM_HI = 0x81000000;

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        dir = new File(args.length > 0 ? args[0] : ".");
        dir.mkdirs();

        di = new DecompInterface();
        di.openProgram(currentProgram);

        line1_mmu();
        line2_vtable();
        line3_namesearch();
        line4_resume();

        di.dispose();
        println("DeepP7 done.");
    }

    // ==================================================================
    // 线 1: MMU 页表定位
    // ==================================================================
    private void line1_mmu() throws Exception {
        PrintWriter p = pw("20_mmu.txt");
        p.println("=== 线1: MMU 页表与运行时地址空间 ===");

        // 1.1 Reset 里那些 DAT_ 到底是什么
        p.println("\n--- 1.1 Reset 用的常量值 ---");
        long[] dats = {0x22c, 0x230, 0x238, 0x23c, 0x240, 0x244, 0x248,
                       0x24c, 0x250, 0x254, 0x258, 0x25c};
        for (long a : dats) {
            Address ad = toAddr(a);
            Object v = getScalar(ad);
            List<String> refs = refsTo(ad);
            p.printf("  DAT_%08x = %-12s refs=%d %s%n", a,
                    v == null ? "(undef)" : "0x" + Long.toHexString(((Number) v).longValue()),
                    refs.size(), refs);
        }

        // 1.2 找页表本体: Reset 往 0x81000000 写了多少项?
        p.println("\n--- 1.2 页表项数量推算 ---");
        p.println("  循环1: puVar3 从 &DAT_81000000 起, uVar4 += 0x100000, 到 uVar4==0 停");
        long n1 = 0;
        for (long u = 0; u != 0; u += 0x100000L) { n1++; if (n1 > 1 << 22) break; }
        p.println("    => 写 " + n1 + " 项 (覆盖 0x" + Long.toHexString(n1 * 0x100000L) + ")");
        p.println("  循环2: puVar5 从 0x80000000 到 0x81000000 步进 0x100000");
        p.println("    => 写 " + ((RAM_HI - RAM_LO) / 0x100000) + " 项");
        p.println("  ★ 结论: 页表覆盖 0x80000000-0x81000000, 共 " +
                ((RAM_HI - RAM_LO) / 0x100000 + n1) + " 个 PTE (每 PTE 映射 1MB)");

        // 1.3 这些 RAM 地址在镜像里有对应吗?
        p.println("\n--- 1.3 RAM 地址是否在镜像内(= 静态地址, 非运行时分配) ---");
        Memory mem = currentProgram.getMemory();
        for (long a : new long[]{RAM_LO, RAM_HI, 0x81000000L, 0x81004000L, 0x806e0000L}) {
            Address ad = toAddr(a);
            boolean inRange = a <= currentProgram.getMaxAddress().getOffset();
            p.printf("  0x%08x : 在镜像内=%s%n", a, inRange ? "YES" : "no (运行时分配)");
        }

        // 1.4 扫镜像里所有指向 0x80000000-0x81000000 的指针(找页表基址候选)
        p.println("\n--- 1.4 扫 RAM 区间指针(找页表存储位置) ---");
        // 用 Ghidra 已定义的数据 + 引用
        DataIterator it = currentProgram.getListing().getDefinedData(true);
        int cnt = 0;
        Map<String, Integer> hist = new TreeMap<>();
        while (it.hasNext()) {
            Data d = it.next();
            if (d.getLength() != 4) continue;
            Object v = d.getValue();
            if (!(v instanceof Number)) continue;
            long val = ((Number) v).longValue();
            if (val >= RAM_LO && val < RAM_HI) {
                cnt++;
                if (cnt <= 40) {
                    List<String> r = refsTo(d.getAddress());
                    p.printf("  %s = 0x%08x  refs=%d %s%n", d.getAddress(), val, r.size(), r);
                }
            }
        }
        p.println("  total scalars pointing into RAM window = " + cnt);

        // 1.5 ★ 关键: 镜像自身加载到哪? 找 0x80000000 附近的 BL 目标
        p.println("\n--- 1.5 BL 目标分布(推断镜像基址) ---");
        int[] buckets = new int[16];
        int totalBL = 0;
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            for (Instruction ins : currentProgram.getListing().getInstructions(f.getBody(), true)) {
                if (!ins.getFlowType().isCall()) continue;
                Address[] flows = ins.getFlows();
                // ★ 间接调用 (BLX reg /  veneer) 可能返回空数组, 必须判长度
                if (flows == null || flows.length == 0) continue;
                long o = flows[0].getOffset();
                totalBL++;
                int b = (int) (o >>> 28);
                if (b < 16) buckets[b]++;
            }
        }
        p.println("  total intra-image calls = " + totalBL);
        for (int b = 0; b < 16; b++) {
            if (buckets[b] == 0) continue;
            p.printf("    target 0x%x??????? : %d (%.1f%%)%n", b,
                    buckets[b], 100.0 * buckets[b] / Math.max(1, totalBL));
        }
        p.close();
    }

    // ==================================================================
    // 线 2: vtable → 构造函数
    // ==================================================================
    private void line2_vtable() throws Exception {
        PrintWriter p = pw("21_vtable_ctor.txt");
        p.println("=== 线2: vtable 候选 → 虚函数 → 构造函数 ===");

        // 收集 >=8 个连续被引用 4 字节标量的段
        List<long[]> cands = new ArrayList<>();
        ReferenceManager rm = currentProgram.getReferenceManager();
        DataIterator it = currentProgram.getListing().getDefinedData(true);
        long[] cur = null;
        long prev = -99;
        List<Address> addrs = new ArrayList<>();
        while (it.hasNext()) {
            Data d = it.next();
            long off = d.getAddress().getOffset();
            boolean hasRef = rm.getReferencesTo(d.getAddress()).hasNext();
            if (hasRef && d.getLength() == 4 && off - prev == 4) {
                if (cur == null) { cur = new long[]{prev, off}; addrs.clear(); addrs.add(toAddr(prev)); }
                cur[1] = off;
                addrs.add(d.getAddress());
            } else {
                if (cur != null && (cur[1] - cur[0]) / 4 + 1 >= 8) cands.add(cur);
                cur = null;
            }
            prev = off;
        }
        if (cur != null && (cur[1] - cur[0]) / 4 + 1 >= 8) cands.add(cur);

        p.println("vtable 候选 (>=8 entries) = " + cands.size());

        // 对每个候选: 看它的 entries 指向哪些函数, 找析构函数特征(调用 operator delete)
        int interesting = 0;
        for (long[] c : cands) {
            int n = (int) ((c[1] - c[0]) / 4 + 1);
            // 读n 个 entry
            List<String> entries = new ArrayList<>();
            Address base = toAddr(c[0]);
            boolean allCode = true;
            for (int i = 0; i < n; i++) {
                Address ea = base.add(i * 4);
                Object v = getScalar(ea);
                if (!(v instanceof Number)) { allCode = false; break; }
                long fv = ((Number) v).longValue();
                if (fv == 0) { entries.add("0"); continue; }
                Function f = getFunctionAt(toAddr(fv & ~1L));
                if (f == null) { allCode = false; entries.add(String.format("0x%x?", fv)); }
                else entries.add(f.getName());
            }
            if (!allCode) continue;      // ★ 只看全部 entry 都是已识别函数的
            interesting++;
            p.printf("%n--- candidate @ 0x%x (%d entries) ---%n", c[0], n);
            for (int i = 0; i < n && i < 20; i++) p.printf("   [%2d] %s%n", i, entries.get(i));
            if (interesting >= 25) { p.println("\n(截断, 只列前 25 个)"); break; }
        }
        p.println("\n全部 entry 落在已识别函数内的候选 = " + interesting);
        p.close();
    }

    // ==================================================================
    // 线 3: 按名字/子串搜伪代码
    // ==================================================================
    private void line3_namesearch() throws Exception {
        PrintWriter p = pw("22_namesearch.txt");
        p.println("=== 线3: 伪代码里的 gamma / color / PostProcess 痕迹 ===");

        String[] keys = {"gamma", "Gamma", "GAMMA", "TC_LOW", "CC_RGB", "SE_MAT",
                         "R2Y_MAT", "PostProcess", "POSTPROCESS", "CWB",
                         "Noisegen", "NOISE", "NOG_", "Recipe", "Material",
                         "IpcGamma", "IpcColor", "IpcWB"};
        Map<String, Integer> hitCount = new TreeMap<>();
        Map<String, List<String>> samples = new HashMap<>();
        for (String k : keys) { hitCount.put(k, 0); samples.put(k, new ArrayList<>()); }

        FunctionIterator fi = currentProgram.getFunctionManager().getFunctions(true);
        int scanned = 0, failed = 0;
        while (fi.hasNext() && scanned < 100000) {
            Function f = fi.next();
            if (f.isThunk() || f.isExternal()) continue;
            if (f.getBody().getNumAddresses() > 20000) continue;   // 跳过超大函数
            scanned++;
            String code = decomp(f);
            if (code == null) { failed++; continue; }
            for (String k : keys) {
                if (!code.contains(k)) continue;
                hitCount.put(k, hitCount.get(k) + 1);
                if (samples.get(k).size() < 6) {
                    // 抓上下文
                    int i = code.indexOf(k);
                    int s = Math.max(0, i - 90), e = Math.min(code.length(), i + 90);
                    samples.get(k).add(f.getName() + " @ " + f.getEntryPoint()
                            + "\n      ..." + code.substring(s, e).replace("\n", "\n      ") + "...");
                }
            }
        }
        p.println("scanned functions = " + scanned + " (decompile failed = " + failed + ")");
        p.println();
        for (String k : keys) {
            int c = hitCount.get(k);
            p.printf("=== %-14s hits=%d ===%n", k, c);
            for (String s : samples.get(k)) p.println("   " + s);
            p.println();
        }
        p.close();
    }

    // ==================================================================
    // 线 4: 续上 Reset 的间接跳转目标
    // ==================================================================
    private void line4_resume() throws Exception {
        PrintWriter p = pw("23_reset_chain.txt");
        p.println("=== 线4: Reset -> (*DAT_0000025c) 后续启动链 ===");

        Object v = getScalar(toAddr(0x25c));
        p.println("DAT_0000025c = " + (v == null ? "(undef)" : "0x" + Long.toHexString(((Number) v).longValue())));

        // Reset 之前那些被调用最多的函数, 反编译后按调用顺序看
        List<Function> fs = new ArrayList<>();
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            if (f.isThunk() || f.isExternal()) continue;
            if (f.getEntryPoint().getOffset() < 0x1000) continue;  // 跳过向量表区
            if (f.getBody().getNumAddresses() > 4000) continue;
            fs.add(f);
        }
        p.println("candidate small functions (<4000 bytes) = " + fs.size());
        p.println("(完整调用图需要 Ghidra 交互分析; 本节留作后续) ");

        // 打印前若干个短函数, 人工找启动链特征
        int n = 0;
        for (Function f : fs) {
            if (f.getBody().getNumAddresses() > 200) continue;
            String c = decomp(f);
            if (c == null) continue;
            if (n < 30) {
                p.printf("%n--- %s @ %s (size %d) ---%n%s%n", f.getName(), f.getEntryPoint(),
                        f.getBody().getNumAddresses(), c.length() > 1500 ? c.substring(0, 1500) + "\n...[truncated]" : c);
            }
            n++;
            if (n >= 60) break;
        }
        p.close();
    }

    // ---- utils ----
    private Object getScalar(Address a) {
        Data d = getDataAt(a);
        if (d != null) {
            Object v = d.getValue();
            if (v instanceof Number) return v;
        }
        try {
            return currentProgram.getMemory().getInt(a);
        } catch (Exception e) {
            return null;
        }
    }

    private String decomp(Function f) {
        String key = f.getEntryPoint().toString();
        if (decompCache.containsKey(key)) return decompCache.get(key);
        String r = null;
        try {
            DecompileResults res = di.decompileFunction(f, 30, monitor);
            if (res != null && res.decompileCompleted()) r = res.getDecompiledFunction().getC();
        } catch (Exception e) { r = null; }
        decompCache.put(key, r);
        return r;
    }

    private PrintWriter pw(String n) throws Exception {
        return new PrintWriter(new FileWriter(new File(dir, n), false));
    }

    private List<String> refsTo(Address a) {
        List<String> out = new ArrayList<>();
        ReferenceIterator rit = currentProgram.getReferenceManager().getReferencesTo(a);
        while (rit.hasNext()) {
            Reference r = rit.next();
            Function f = getFunctionContaining(r.getFromAddress());
            out.add(f == null ? r.getFromAddress().toString() : f.getName());
            if (out.size() >= 6) break;
        }
        return out;
    }
}
