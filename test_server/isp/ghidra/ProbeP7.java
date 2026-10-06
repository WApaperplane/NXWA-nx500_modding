// P7 深度分析：验证"死数据"结论 + 找 gamma/color 真实引用
// 思路: 不用字符串当锚点（已证伪），改用
//   ①Ghidra 自动定义的字符串表 ②从 decompiler 输出找函数
//   ③按常量指纹定位（44 锚点/3x3 矩阵这类结构在代码里的引用）
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

public class ProbeP7 extends GhidraScript {

    private File dir;

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        dir = new File(args.length > 0 ? args[0] : ".");
        dir.mkdirs();

        controlTest();
        stringXrefStats();
        searchGammaAnchors();
        decompileHotFuncs();
        findVtables();
    }

    // ==== 判据 1: 对照组 —— 确认 Ghidra 的 xref 机制本身能工作 ====
    private void controlTest() throws Exception {
        PrintWriter p = pw("10_control.txt");
        p.println("=== 对照组: 确认 Ghidra 引用机制有效 ===");
        p.println("如果这些\"早期字符串\"(0x8494COMPARE 等)有引用 => 机制有效");
        p.println("如果连它们都0 => Ghidra 没建立引用, 是工具问题而非目标问题");
        p.println();
        String[] ctrl = {"COMPARE", "Call stack dump", "Undefined SWI", "0123456789ABCDEF",
                         "Notify system fault to A9", "A7 core's log"};
        for (String s : ctrl) {
            Address a = findStr(s);
            if (a == null) { p.println(String.format("%-30s NOT FOUND", s)); continue; }
            List<String> refs = refsTo(a);
            p.println(String.format("%-30s @ %s  refs=%d  %s", s, a, refs.size(), refs));
        }
        p.close();
    }

    // ==== 判据 2: 全量字符串引用率统计 ====
    private void stringXrefStats() throws Exception {
        PrintWriter p = pw("11_string_xref_stats.txt");
        p.println("=== 全量字符串引用率 ===");
        DataIterator it = currentProgram.getListing().getDefinedData(true);
        int total = 0, withRefs = 0, addrInRange = 0;
        List<String> withRefSamples = new ArrayList<>();
        ReferenceManager rm = currentProgram.getReferenceManager();
        while (it.hasNext()) {
            Data d = it.next();
            String dn = d.getDataType().getName().toLowerCase();
            if (!dn.contains("string") && !dn.contains("unicode")) continue;
            total++;
            Address a = d.getAddress();
            if (a.getOffset() >= 0x580000L) addrInRange++;
            ReferenceIterator rit = rm.getReferencesTo(a);
            if (rit.hasNext()) {
                withRefs++;
                if (withRefSamples.size() < 60) {
                    List<String> f = refsTo(a);
                    withRefSamples.add(a + " \"" + trunc(d) + "\" -> " + f);
                }
            }
        }
        p.println("defined strings total = " + total);
        p.println("in 0x580000+ (symbol区) = " + addrInRange);
        p.println("with >=1 reference       = " + withRefs);
        p.println(String.format("reference rate           = %.2f%%", 100.0 * withRefs / Math.max(1, total)));
        p.println();
        p.println("=== 有引用的字符串样本 (最多60) ===");
        for (String s : withRefSamples) p.println(s);
        p.close();
    }

    // ==== 判据 3: gamma/color 锚点结构的常量指纹 ====
    // TC_LOW_ANCHOR 44 个锚点: 若 ISP 内部按数组索引访问, 代码里会出现
    // 44*4=176 或 0x14 步长相关的常量
    private void searchGammaAnchors() throws Exception {
        PrintWriter p = pw("12_gamma_anchor_probe.txt");
        p.println("=== gamma 锚点/矩阵的常量指纹搜索 ===");
        p.println("（这次有 Ghidra 的段边界+函数识别做前提, 结论可信）");
        p.println();

        // 找所有引用了 0x754188 附近地址的标量（Ghidra 已定义的数据）
        p.println("--- 引用 0x754000-0x755FFF 区间的标量 ---");
        DataIterator it = currentProgram.getListing().getDefinedData(true);
        int found = 0;
        for (int page = 0x754000; page < 0x756000; page += 0x1000) {
            final int pg = page;
            while (it.hasNext()) {
                Data d = it.next();
                Address a = d.getAddress();
                if (a.getOffset() < pg || a.getOffset() >= pg + 0x1000) continue;
                List<String> refs = refsTo(a);
                if (refs.isEmpty()) continue;
                found++;
                p.println(String.format("  %s = %s  refs=%d %s", a, d.getValue(), refs.size(), refs));
            }
        }
        p.println("total referenced scalars in 0x754000-0x755FFF = " + found);
        p.close();
    }

    // ==== 判据 4: 反编译关键函数, 看真实的 gamma/color 处理 ====
    private void decompileHotFuncs() throws Exception {
        PrintWriter p = pw("13_decompiled.txt");
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        DecompileOptions opts = new DecompileOptions();

        // 优先反编译: Reset 之后的初始化链 + 引用最多的函数
        List<Function> targets = pickTargets();
        p.println("=== 反编译 " + targets.size() + " 个目标函数 ===");
        for (Function f : targets) {
            p.println("\n" + repeat('=', 78));
            p.println("FUNCTION " + f.getName() + " @ " + f.getEntryPoint()
                    + " size=" + f.getBody().getNumAddresses());
            p.println(repeat('=', 78));
            DecompileResults res = di.decompileFunction(f, 60, monitor);
            if (res != null && res.decompileCompleted()) {
                p.println(res.getDecompiledFunction().getC());
            } else {
                p.println("(decompile failed: " + (res == null ? "null" : res.getErrorMessage()) + ")");
            }
        }
        di.dispose();
        p.close();
    }

    // 选目标: Reset 链+ 被引用最多的几个函数
    private List<Function> pickTargets() {
        Map<String, Integer> score = new HashMap<>();
        ReferenceManager rm = currentProgram.getReferenceManager();
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            if (f.isThunk() || f.isExternal()) continue;
            int n = 0;
            ReferenceIterator rit = rm.getReferencesTo(f.getEntryPoint());
            while (rit.hasNext()) { rit.next(); n++; }
            if (n > 0) score.put(f.getEntryPoint().toString(), n);
        }
        List<Map.Entry<String, Integer>> es = new ArrayList<>(score.entrySet());
        es.sort((x, y) -> y.getValue() - x.getValue());
        List<Function> out = new ArrayList<>();
        // 前 12 个高引用函数
        for (int i = 0; i < Math.min(12, es.size()); i++) {
            Address a = toAddr(es.get(i).getKey());
            Function f = getFunctionAt(a);
            if (f != null) out.add(f);
        }
        // 加Reset
        Function rst = getFunctionAt(toAddr(0x140));
        if (rst != null) out.add(0, rst);
        return out;
    }

    // ==== 判据 5: vtable 搜索 (C++ 类的静态表) ====
    private void findVtables() throws Exception {
        PrintWriter p = pw("14_vtables.txt");
        p.println("=== vtable 候选: 连续的被引用地址序列 ===");
        ReferenceManager rm = currentProgram.getReferenceManager();
        DataIterator it = currentProgram.getListing().getDefinedData(true);
        List<long[]> seqs = new ArrayList<>();
        long[] cur = null;
        long prev = -99;
        while (it.hasNext()) {
            Data d = it.next();
            long off = d.getAddress().getOffset();
            boolean hasRef = rm.getReferencesTo(d.getAddress()).hasNext();
            if (hasRef && d.getLength() == 4 && off - prev == 4) {
                if (cur == null) cur = new long[]{prev, off};
                else cur[1] = off;
            } else {
                if (cur != null && cur[1] - cur[0] >= 16) seqs.add(cur);
                cur = null;
            }
            prev = off;
        }
        if (cur != null && cur[1] - cur[0] >= 16) seqs.add(cur);
        p.println("候选 vtable 段(>=5 个连续 4 字节被引用标量) = " + seqs.size());
        for (long[] s : seqs) {
            p.println(String.format("  %s - %s  (%d entries)", hex(s[0]), hex(s[1]), (s[1] - s[0]) / 4 + 1));
        }
        p.close();
    }

    // ---- utils ----
    private PrintWriter pw(String n) throws Exception {
        return new PrintWriter(new FileWriter(new File(dir, n), false));
    }
    private String repeat(char c, int n) {
        StringBuilder sb = new StringBuilder(); for (int i = 0; i < n; i++) sb.append(c); return sb.toString();
    }
    private String hex(long v) { return String.format("0x%x", v); }
    private String trunc(Data d) {
        Object v = d.getValue();
        String s = v == null ? "" : v.toString();
        s = s.replace("\n", "\\n");
        return s.length() > 48 ? s.substring(0, 48) : s;
    }
    private List<String> refsTo(Address a) {
        List<String> out = new ArrayList<>();
        ReferenceIterator rit = currentProgram.getReferenceManager().getReferencesTo(a);
        while (rit.hasNext()) {
            Reference r = rit.next();
            Function f = getFunctionContaining(r.getFromAddress());
            out.add(f == null ? r.getFromAddress().toString() : f.getName());
            if (out.size() >= 8) break;
        }
        return out;
    }
    private Address findStr(String s) {
        byte[] t;
        try { t = s.getBytes("ASCII"); } catch (Exception e) { return null; }
        byte[] w = Arrays.copyOf(t, t.length + 1);
        for (MemoryBlock blk : currentProgram.getMemory().getBlocks()) {
            if (!blk.isInitialized()) continue;
            try {
                int n = (int) Math.min(blk.getSize(), 0x1000000);
                byte[] buf = new byte[n];
                currentProgram.getMemory().getBytes(blk.getStart(), buf);
                for (int i = 0; i + w.length <= n; i++) {
                    boolean ok = true;
                    for (int j = 0; j < w.length; j++) if (buf[i + j] != w[j]) { ok = false; break; }
                    if (ok) return blk.getStart().add(i);
                }
            } catch (Exception e) { }
        }
        return null;
    }
}
