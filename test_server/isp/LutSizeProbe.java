// LutSizeProbe.java —— 定位 p7 里 3D LUT 表长上限的唯一校验点
// 目标：找到 "lut size error too large~ (%d) > %d" 的引用函数，
//       并把它附近的所有常量/比较值导出来 —— 那是硬件表长的硬上限。
// @category NXKS2
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.mem.Memory;
import ghidra.app.decompiler.*;
import java.util.*;

public class LutSizeProbe extends GhidraScript {

    private String[] TARGETS = {
        "lut size error too large",       // ★ 表长上限校验
        "lv1 data size = ",               // ★ 数据源 1
        "lv2 data size = ",
        "lv3 data size = ",
        "4k1 data size = ",
        "4k2 data size = ",
        "ud2 data size = ",
        "burst data size = ",
        "lut size error",
        "3dlut load Done",
        "live data size = "
    };

    @Override
    public void run() throws Exception {
        StringBuilder sb = new StringBuilder();
        sb.append("=== LutSizeProbe ===\n");
        Memory mem = currentProgram.getMemory();
        Listing lst = currentProgram.getListing();
        ReferenceManager rm = currentProgram.getReferenceManager();

        // 1) 先把所有目标字符串的地址找出来
        Map<String, Address> strAddr = new LinkedHashMap<>();
        DataIterator it = lst.getDefinedData(true);
        int scanned = 0;
        int cap = 400000;   // ★ 上限：字符串通常在 20000 条内，防止遍历整个镜像
        while (it.hasNext() && !monitor.isCancelled() && scanned < cap) {
            Data d = it.next();
            if (d.getDataType() == null) continue;
            String t = d.getDataType().getName().toLowerCase();
            if (!t.startsWith("string") && !t.contains("unicode") && !t.contains("char"))
                continue;
            scanned++;
            Object v = d.getValue();
            if (!(v instanceof String)) continue;
            String s = (String) v;
            for (String tg : TARGETS) {
                if (s.toLowerCase().contains(tg.toLowerCase()) && !strAddr.containsKey(tg)) {
                    strAddr.put(tg, d.getAddress());
                    sb.append(String.format("STR  %-26s @ %s%n", tg, d.getAddress()));
                }
            }
        }
        sb.append(String.format("(%d strings scanned)%n%n", scanned));

        if (strAddr.isEmpty()) {
            sb.append("★ 没找到任何目标字符串 —— 可能 DataIterator 没覆盖 .rodata\n");
            println(sb.toString());
            return;
        }

        // 2) 对每个字符串取引用者（函数）
        Set<Function> funcs = new LinkedHashSet<>();
        Map<Function, List<String>> funcHits = new LinkedHashMap<>();
        for (Map.Entry<String, Address> e : strAddr.entrySet()) {
            // ★ Ghidra 12.x：getReferencesTo(Address) 返回 ReferenceIterator（不是数组）
            ReferenceIterator rit = rm.getReferencesTo(e.getValue());
            int nref = 0;
            while (rit != null && rit.hasNext()) {
                Reference r = rit.next();
                nref++;
                Address from = r.getFromAddress();
                Function f = lst.getFunctionContaining(from);
                sb.append(String.format("XREF %-24s from %s  func=%s%n",
                        e.getKey(), from,
                        f == null ? "(none)" : f.getName() + "@" + f.getEntryPoint()));
                if (f != null) {
                    funcs.add(f);
                    funcHits.computeIfAbsent(f, k -> new ArrayList<>()).add(e.getKey());
                }
            }
            sb.append(String.format("     (%s 共 %d 个引用)%n", e.getKey(), nref));
        }
        sb.append(String.format("%n(%d unique functions)%n%n", funcs.size()));

        // 3) 导出这些函数的伪代码 + 附近标量
        DecompInterface di = new DecompInterface();
        DecompileOptions opts = new DecompileOptions();
        di.setOptions(opts);
        di.openProgram(currentProgram);

        int idx = 0;
        for (Function f : funcs) {
            if (monitor.isCancelled()) break;
            idx++;
            sb.append("\n" + "=".repeat(70) + "\n");
            sb.append(String.format("#%d  %s @ %s   [size=%d]%n", idx,
                    f.getName(), f.getEntryPoint(), f.getBody().getNumAddresses()));
            sb.append("  hits: " + funcHits.get(f) + "\n");
            sb.append("=".repeat(70) + "\n");
            DecompileResults res = di.decompileFunction(f, 60, monitor);
            if (res != null && res.decompileCompleted() && res.getDecompiledFunction() != null) {
                sb.append(res.getDecompiledFunction().getC());
            } else {
                sb.append("  (decompile failed: " + (res == null ? "null" : res.getErrorMessage()) + ")\n");
            }
        }
        di.dispose();

        // 4) 额外：只扫【上面已定位的函数】里的立即数，不做全程序扫描
        //    （全程序 16468 函数 × 指令逐条遍历会跑十几分钟，且没必要）
        sb.append("\n\n=== 目标函数内的立即数（表长候选）===\n");
        int[] cands = {29478, 19652, 215622, 4913, 9826, 14739, 344, 688, 4096, 32768, 262144};
        for (Function f : funcs) {
            InstructionIterator ii = lst.getInstructions(f.getBody(), true);
            while (ii.hasNext()) {
                Instruction ins = ii.next();
                int nops = ins.getNumOperands();
                for (int k = 0; k < nops; k++) {
                    // ★ Instruction 没有 getOpValue()，用 getOpObjects()
                    Object[] objs = ins.getOpObjects(k);
                    if (objs == null) continue;
                    for (Object ov : objs) {
                        if (!(ov instanceof Long)) continue;
                        long v = (Long) ov;
                        for (int c : cands) {
                            if (v == (long) c) {
                                sb.append(String.format("  %d (=0x%x)  @ %s   %s   [%s]%n",
                                        c, c, ins.getAddress(), ins.toString(),
                                        f.getName()));
                            }
                        }
                    }
                }
            }
        }

        java.io.File out = new java.io.File("E:\\ghidra_out\\lutsize_probe.txt");
        java.io.PrintWriter pw = new java.io.PrintWriter(out, "UTF-8");
        pw.print(sb);
        pw.close();
        println("written: " + out.getAbsolutePath() + "  (" + out.length() + " bytes)");
    }

    private String f2(Address a) {
        String s = a.toString();
        return s.length() > 6 ? s : ("00000" + s);
    }
}
