@ =============================================================================
@ a1_harness.s —— A1 p7 归一化器「包级真字节」QEMU 行为测试载具
@ =============================================================================
@ 组装方式（见 build_a1_qemu.sh）：.incbin 引入从 SLP 成品包解出的真实字节——
@     seg_norm.bin = p7[0x51090..0x513e0]（归一化器全链：入口/47项表/handler/拒收）
@     seg_blk.bin  = p7[0x11504..0x1151c]（特判块 / step1 中转）
@ 运行方式（qemu-arm-static；无 libc；裸 svc）：
@     1) mmap2(0x80000000, 0x80000, RWX, FIXED|PRIVATE|ANON, -1, 0)  铺出 p7 地址空间
@     2) 拷  norm → 0x80051090；blk → 0x80011504；日志桩 → 0x80046484
@     3) 遍历 64 用例：blx 0x80051090（真实 VA 的归一化器入口）
@        记录 {id, ret, conv}；拒收路径经 bl 0x80046484 —— 桩在 0x80070000 计数
@     4) write(1, outbuf, 64*12+4) —— 尾部 4B = 日志桩调用计数
@ 断言（由 check_a1_qemu.py 判定）：
@     step1 ≡ orig（全 64 例）；full 除 0x130..0x133 外 ≡ orig；0x130..0x133 → ret=0, conv=id
@ 寄存器纪律：被调链（0x80051090 全链）只用 r0-r3；r4/r5/r6/r8 为 harness 跨调用状态，
@             r9 为每轮重设的 scratch。
@
@ 构建: arm-linux-gnueabihf-as -o h.o harness.s && arm-linux-gnueabihf-ld -Ttext=0x10000 -e _start -o h.elf h.o
@ =============================================================================

	.arch armv7-a
	.arm
	.equ	NORM_VA,   0x80051090
	.equ	BLK_VA,    0x80011504
	.equ	LOG_VA,    0x80046484
	.equ	CNT_VA,    0x80070000
	.equ	NR_MMAP2,  192
	.equ	NR_WRITE,  4
	.equ	NR_EXIT,   1

	.text
	.global _start
_start:
	ldr	sp, =stack_top

	@ ---- 1) mmap2(0x80000000, 0x80000, PROT RWX, MAP FIXED|PRIVATE|ANON, -1, 0) ----
	ldr	r0, =0x80000000
	ldr	r1, =0x80000
	mov	r2, #7			@ PROT_READ|WRITE|EXEC
	ldr	r3, =0x32		@ MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED
	mvn	r4, #0			@ fd = -1
	mov	r5, #0			@ offset = 0（页单位）
	mov	r7, #NR_MMAP2
	svc	#0
	ldr	r6, =0x80000000
	cmp	r0, r6
	bne	L_fail			@ 必须精确落在 0x80000000

	@ ---- 2a) norm 区 → 0x80051090（212 words） ----
	ldr	r1, =norm_seg
	ldr	r3, =NORM_VA
	mov	r2, #212		@ 0x350/4
L_c1:	ldr	r4, [r1], #4
	str	r4, [r3], #4
	subs	r2, r2, #1
	bne	L_c1

	@ ---- 2b) blk 区 → 0x80011504（6 words） ----
	ldr	r1, =blk_seg
	ldr	r3, =BLK_VA
	mov	r2, #6			@ 24/4
L_c2:	ldr	r4, [r1], #4
	str	r4, [r3], #4
	subs	r2, r2, #1
	bne	L_c2

	@ ---- 2c) 日志桩 → 0x80046484（6 words） ----
	ldr	r1, =log_stub_src
	ldr	r3, =LOG_VA
	mov	r2, #6			@ 24/4
L_c3:	ldr	r4, [r1], #4
	str	r4, [r3], #4
	subs	r2, r2, #1
	bne	L_c3

	@ ---- 3) 用例循环 ----
	ldr	r4, =cases
	ldr	r5, =outbuf
	ldr	r8, =casecount
	ldr	r8, [r8]
L_loop:
	ldr	r0, [r4], #4		@ id
	str	r0, [r5]		@ out[0] = id
	ldr	r6, =convbuf
	ldr	r9, =0xdeadbeef
	str	r9, [r6]		@ conv 哨兵（拒收时应保持？不——拒收会写 0xff）
	mov	r1, r6
	ldr	r9, =NORM_VA
	blx	r9			@ ★ 调用真实字节的归一化器
	str	r0, [r5, #4]		@ out[1] = ret
	ldr	r9, [r6]
	str	r9, [r5, #8]		@ out[2] = conv
	add	r5, r5, #12
	subs	r8, r8, #1
	bne	L_loop

	@ ---- 3b) 追加日志桩调用计数 ----
	ldr	r9, =CNT_VA
	ldr	r9, [r9]
	str	r9, [r5]

	@ ---- 4) write(1, outbuf, casecount*12 + 4) ----
	mov	r0, #1
	ldr	r1, =outbuf
	ldr	r2, =casecount
	ldr	r2, [r2]
	mov	r3, #12
	mul	r2, r3, r2
	add	r2, r2, #4
	mov	r7, #NR_WRITE
	svc	#0

	mov	r0, #0
	mov	r7, #NR_EXIT
	svc	#0

L_fail:
	@ mmap 失败：输出 "MMAPFAIL" + 4B 负错误码，exit 9
	mov	r6, r0
	mov	r0, #1
	ldr	r1, =failmsg
	mov	r2, #8
	mov	r7, #NR_WRITE
	svc	#0
	ldr	r1, =outbuf
	str	r6, [r1]
	mov	r0, #1
	ldr	r1, =outbuf
	mov	r2, #4
	mov	r7, #NR_WRITE
	svc	#0
	mov	r0, #9
	mov	r7, #NR_EXIT
	svc	#0

@ ---- 日志桩 24B（拷到 0x80046484 执行；movw/movt 内嵌常量 ⇒ 位置无关） ----
@ 拒收 handler 在 bl 前已完成 conv=0xff 写入；此桩只做计数，r0-r3 随 caller-saved 约定。
	.align 4
log_stub_src:
	movw	r2, #0x0000
	movt	r2, #0x8007
	ldr	r1, [r2]
	add	r1, r1, #1
	str	r1, [r2]
	bx	lr

@ ---- 常量与用例数据 ----
	.section .rodata
	.align 4
norm_seg:
	.incbin "seg_norm.bin"
	.align 4
blk_seg:
	.incbin "seg_blk.bin"

	.align 4
failmsg:
	.ascii "MMAPFAIL"

	.align 4
cases:
	@ 1) 47 项跳转表全域 0x100..0x12e
	.word	0x100,0x101,0x102,0x103,0x104,0x105,0x106,0x107
	.word	0x108,0x109,0x10a,0x10b,0x10c,0x10d,0x10e,0x10f
	.word	0x110,0x111,0x112,0x113,0x114,0x115,0x116,0x117
	.word	0x118,0x119,0x11a,0x11b,0x11c,0x11d,0x11e,0x11f
	.word	0x120,0x121,0x122,0x123,0x124,0x125,0x126,0x127
	.word	0x128,0x129,0x12a,0x12b,0x12c,0x12d,0x12e
	@ 2) A1 目标四维（full 应恒等放行；orig/step1 应拒收）
	.word	0x130,0x131,0x132,0x133
	@ 3) 相邻边界
	.word	0x12f,0x134,0x135,0x1ff,0x200
	@ 4) 远端
	.word	0x3ff,0x1000,0xffff
	@ 5) 极端值（含 0 与 32 位回绕）
	.word	0x0,0x7fffffff,0x80000000,0xfffffffe,0xffffffff
cases_end:
casecount:
	.word	(cases_end - cases)/4

	.section .bss
	.align 4
convbuf:	.skip 4
outbuf:		.skip 800
stack:		.skip 8192
stack_top:
