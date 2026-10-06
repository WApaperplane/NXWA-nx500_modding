// P7: 反编译 SMA 引用者 + 内存映射表消费者 + 浮点表候选验证
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

public class SmaDeepP7 extends GhidraScript {

    private File dir;
    private DecompInterface di;
    private Map<String, String> cache = new HashMap<>();
    private byte[] img;

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        dir = new File(args.length > 0 ? args[0] : ".");
        dir.mkdirs();
        di = new DecompInterface();
        di.openProgram(currentProgram);
        img = new byte[(int) (currentProgram.getMaxAddress().getOffset() + 1)];
        currentProgram.getMemory().getBytes(toAddr(0), img);

        smaConsumers();
        mapConsumers();
        floatCandidates();

        di.dispose();
        println("SmaDeepP7 done.");
    }

    // ==== 1. 反编译引用 SMA 0x9fc0 的两个函数 ====
    private void smaConsumers() throws Exception {
        PrintWriter p = pw("40_sma_consumers.txt");
        p.println("=== 引用 0x9fc0 (SMA_BASE) 的两个函数 ===");
        long[] froms = {0x00a75bd2L, 0x009995f0L};
        for (long fr : froms) {
            Address a = toAddr(fr);
            Function f = getFunctionContaining(a);
            p.printf("%n########## ref at 0x%x in %s ##########%n", fr, f == null ? "(no func)" : f.getName());
            if (f == null) continue;
            p.printf("function %s @ %s size=%d%n", f.getName(), f.getEntryPoint(), f.getBody().getNumAddresses());
            String c = decomp(f);
            p.println(c == null ? "(decompile failed)" : c);
            // 打印被引用指令附近的反汇编
            p.println("--- 引用点附近反汇编 ---");
            Instruction ins = getInstructionAt(a);
            if (ins == null) p.println("  (no instruction at ref addr; ref可能来自数据)");
            else {
                Instruction start = ins;
                for (int i = 0; i < 6 && start.getPrevious() != null; i++) start = start.getPrevious();
                for (Instruction q = start; q != null; q = q.getNext()) {
                    String mark = q.getAddress().equals(a) ? "  <<<" : "";
                    p.printf("  %s  %s%s%n", q.getAddress(), q.toString(), mark);
                    if (q.getAddress().getOffset() > a.getOffset() + 24) break;
                }
            }
        }
        p.close();
    }

    // ==== 2. 内存映射表的其他消费者 ====
    private void mapConsumers() throws Exception {
        PrintWriter p = pw("41_map_consumers.txt");
        p.println("=== 内存映射表消费者（FUN_0012a440 等）===");
        long[] refs = {0xa000L, 0xa010L, 0xa020L, 0xa030L};
        for (long t : refs) {
            ReferenceIterator rit = currentProgram.getReferenceManager().getReferencesTo(toAddr(t));
            List<Function> fs = new ArrayList<>();
            while (rit.hasNext()) {
                Reference r = rit.next();
                Function f = getFunctionContaining(r.getFromAddress());
                if (f != null && !fs.contains(f)) fs.add(f);
            }
            p.printf("%n--- table entry 0x%x : %d 个引用函数 ---%n", t, fs.size());
            for (Function f : fs) {
                p.printf("  %s @ %s size=%d%n", f.getName(), f.getEntryPoint(), f.getBody().getNumAddresses());
            }
            // 只反编译第一个（看它怎么用这张表）
            if (!fs.isEmpty()) {
                Function f = fs.get(0);
                p.println("--- 反编译 " + f.getName() + " ---");
                String c = decomp(f);
                p.println(c == null ? "(failed)" : (c.length() > 6000 ? c.substring(0, 6000) + "\n...[truncated]" : c));
            }
        }
        p.close();
    }

    // ==== 3. 浮点表候选：过滤掉噪声, 只留"被引用"的 ====
    private void floatCandidates() throws Exception {
        PrintWriter p = pw("42_float_cands.txt");
        p.println("=== 浮点表候选（只保留有代码引用的）===");

        p.println("\n--- 3x3 矩阵候选：连续 9 个 |v|<=4 的 float，且首地址有引用 ---");
        p.println("（★ 关键过滤：只保留 refs>0 的，纯数据区无引用的不算）");
        int tot = 0, kept = 0;
        int i = 0;
        List<long[]> cands = new ArrayList<>();
        while (i + 9 * 4 <= img.length) {
            boolean ok = true;
            for (int k = 0; k < 9; k++) {
                float v = f(i + k * 4L);
                if (Float.isNaN(v) || Float.isInfinite(v) || Math.abs(v) > 4.0) { ok = false; break; }
            }
            if (ok) { cands.add(new long[]{i}); i += 36; } else i += 4;
        }
        tot = cands.size();
        p.println("  原始候选 = " + tot);
        for (long[] c : cands) {
            List<String> r = refsTo(toAddr(c[0]));
            if (r.isEmpty()) continue;
            kept++;
            if (kept <= 40) {
                StringBuilder sb = new StringBuilder();
                for (int k = 0; k < 9; k++) sb.append(String.format("%.4f ", f(c[0] + k * 4L)));
                p.printf("  0x%x: [%s] refs=%d %s%n", c[0], sb.toString().trim(), r.size(), r);
            }
        }
        p.println("  有引用的 = " + kept);

        p.println("\n--- gamma 锚点候选：连续 22 个 [0,1] float，且首地址有引用 ---");
        int tot2 = 0, kept2 = 0;
        i = 0;
        List<Long> c2 = new ArrayList<>();
        while (i + 22 * 4 <= img.length) {
            boolean ok = true;
            for (int k = 0; k < 22; k++) {
                float v = f(i + k * 4L);
                if (Float.isNaN(v) || Float.isInfinite(v) || v < -0.001f || v > 1.001f) { ok = false; break; }
            }
            if (ok) { c2.add((long) i); i += 88; } else i += 4;
        }
        tot2 = c2.size();
        p.println("  原始候选 = " + tot2);
        for (long off : c2) {
            List<String> r = refsTo(toAddr(off));
            if (r.isEmpty()) continue;
            kept2++;
            if (kept2 <= 30) {
                StringBuilder sb = new StringBuilder();
                for (int k = 0; k < 8; k++) sb.append(String.format("%.3f ", f(off + k * 4L)));
                sb.append("... ");
                for (int k = 20; k < 22; k++) sb.append(String.format("%.3f", f(off + k * 4L)));
                p.printf("  0x%x: [%s] refs=%d %s%n", off, sb.toString().trim(), r.size(), r);
            }
        }
        p.println("  有引用的 = " + kept2);

        // 对照: 8连[0,1] 与 16连[0,1] 的有引用数（看是否有明显峰值）
        for (int n : new int[]{8, 12, 16, 20, 22, 24, 32, 44, 88}) {
            int c = 0;
            i = 0;
            while (i + n * 4 <= img.length) {
                boolean ok = true;
                for (int k = 0; k < n; k++) {
                    float v = f(i + k * 4L);
                    if (Float.isNaN(v) || Float.isInfinite(v) || v < -0.001f || v > 1.001f) { ok = false; break; }
                }
                if (ok) { if (!refsTo(toAddr(i)).isEmpty()) c++; i += n * 4; } else i += 4;
            }
            p.printf("  n=%-3d 有引用的 [0,1] float 连续段 = %d%n", n, c);
        }
        p.close();
    }

    // ---- utils ----
    private float f(long off) {
        int i = (int) off;
        if (i < 0 || i + 4 > img.length) return Float.NaN;
        return Float.intBitsToFloat(
            (img[i] & 0xff) | ((img[i+1] & 0xff) << 8) | ((img[i+2] & 0xff) << 16) | ((img[i+3] & 0xff) << 24));
    }

    private String decomp(Function f) {
        String key = f.getEntryPoint().toString();
        if (cache.containsKey(key)) return cache.get(key);
        String r = null;
        try {
            DecompileResults res = di.decompileFunction(f, 60, monitor);
            if (res != null && res.decompileCompleted()) r = res.getDecompiledFunction().getC();
        } catch (Exception e) { r = null; }
        cache.put(key, r);
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
            if (r.getReferenceType().isData()) { /* 保留 */ }
            Function f = getFunctionContaining(r.getFromAddress());
            out.add(f == null ? r.getFromAddress().toString() : f.getName());
            if (out.size() >= 6) break;
        }
        return out;
    }
}
