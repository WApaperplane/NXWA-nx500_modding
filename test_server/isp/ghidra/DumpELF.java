// DumpELF.java — 通用 ELF 导出脚本（相机用户态二进制专用，适配 Ghidra 12.x）
// 用法: analyzeHeadless <proj> <name> -process <file> -noanalysis -scriptPath <dir> \
//         -postScript DumpELF.java <outDir> [maxDecompiled] [decompileFilter]
// 产出: <outDir>/<progName>_dump/{00_header,01_memory_blocks,02_functions,03_strings,04_decompiled.c}
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.DataIterator;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.Program;
import ghidra.program.model.mem.MemoryBlock;
import java.io.File;
import java.io.PrintWriter;

public class DumpELF extends GhidraScript {

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String outDir = (args.length > 0) ? args[0] : "E:/ghidra_out";
        int maxDecomp = (args.length > 1) ? Integer.parseInt(args[1]) : 2500;
        String filter = (args.length > 2) ? args[2] : "";   // 仅反编译名字含该串的函数（空=全部）

        Program prog = currentProgram;
        String progName = prog.getName();
        File dir = new File(outDir, progName + "_dump");
        dir.mkdirs();
        println("== DumpELF: " + progName + " -> " + dir.getAbsolutePath());

        // 00 header
        try (PrintWriter fw = new PrintWriter(new File(dir, "00_header.txt"))) {
            fw.println("Program: " + progName);
            fw.println("Executable path: " + prog.getExecutablePath());
            fw.println("Language: " + prog.getLanguageID());
            fw.println("Compiler: " + prog.getCompilerSpec().getCompilerSpecID());
            fw.println("ImageBase: " + prog.getImageBase());
            try { fw.println("MD5: " + prog.getExecutableMD5()); } catch (Throwable t) { fw.println("MD5: n/a"); }
        }

        // 01 memory blocks
        try (PrintWriter fw = new PrintWriter(new File(dir, "01_memory_blocks.txt"))) {
            for (MemoryBlock b : prog.getMemory().getBlocks()) {
                fw.println(String.format("%-12s %s - %s  r=%b w=%b x=%b init=%b",
                        b.getName(), b.getStart(), b.getEnd(),
                        b.isRead(), b.isWrite(), b.isExecute(), b.isInitialized()));
            }
        }

        // 02 functions
        FunctionManager fm = prog.getFunctionManager();
        int nf = 0;
        try (PrintWriter fw = new PrintWriter(new File(dir, "02_functions.txt"))) {
            for (Function f : fm.getFunctions(true)) {
                fw.println(f.getEntryPoint() + "  " + f.getName() + "  size=" + f.getBody().getNumAddresses());
                nf++;
            }
        }
        println("functions: " + nf);

        // 03 strings
        int ns = 0;
        try (PrintWriter fw = new PrintWriter(new File(dir, "03_strings.txt"))) {
            DataIterator di = prog.getListing().getDefinedData(true);
            while (di.hasNext()) {
                Data d = di.next();
                Object v = d.getValue();
                if (v instanceof String) {
                    fw.println(d.getAddress() + "  " + v);
                    ns++;
                }
            }
        }
        println("strings: " + ns);

        // 04 decompile
        DecompInterface dec = new DecompInterface();
        dec.setOptions(new ghidra.app.decompiler.DecompileOptions());
        dec.toggleCCode(true);
        dec.openProgram(prog);
        int nd = 0, nskip = 0;
        try (PrintWriter fw = new PrintWriter(new File(dir, "04_decompiled.c"))) {
            for (Function f : fm.getFunctions(true)) {
                if (f.isThunk() || f.isExternal()) continue;
                if (!filter.isEmpty() && !f.getName().contains(filter)) { nskip++; continue; }
                if (nd >= maxDecomp) { fw.println("// TRUNCATED at " + maxDecomp + " functions"); break; }
                DecompileResults res = dec.decompileFunction(f, 60, monitor);
                if (res != null && res.decompileCompleted()) {
                    fw.println("//==== " + f.getName() + " @ " + f.getEntryPoint() + "  size=" + f.getBody().getNumAddresses() + " ====");
                    fw.println(res.getDecompiledFunction().getC());
                    nd++;
                }
            }
        }
        println("decompiled: " + nd + " (skipped by filter: " + nskip + ")");
        println("DUMP-COMPLETE " + dir.getAbsolutePath());
    }
}
