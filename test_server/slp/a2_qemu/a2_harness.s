@ =============================================================================
@ a2_harness.s —— A2 补丁「真字节」QEMU 验证载具（qemu-arm-static）
@ =============================================================================
@ 被测（从 p7_a2.bin 提取的真字节）：
@   seg_norm  0x51090（归一化器全链——含 0x51394 拒收 handler）
@   seg_11500 0x11504（A1 块·改扩版）+ 0x11530（A2 块）
@   seg_wrap  0x4ccf4 区（外部写包装 + 字面量池）
@ 桩（写入目标地址；movw/movt 常量，位置无关）：
@   0x80046484  日志 → 事件 type=4
@   0x800d69cc  锁/对象 → 返回 0x8142ab20
@   0x80064f0c  写槽 → 捕获 (slot, val) → type=1
@   0x80051ab8  应用 → type=2
@   0x800d6b20  变量发送 → 捕获 (id, *ptr, obj) → type=3
@ 事件区：0x80090000（count）+ 0x80090004（16B×64：{type,a,b,c}）
@ 主循环：对每用例 (id, val)：r0=id, r1=&valbuf, r2=4 → blx 0x4ccf4 → 记录
@ 输出：u32 ncase | ncase×16B {id,ret,before,after} | u32 nevent | nevent×16B {type,a,b,c}
@ =============================================================================

	.arch armv7-a
	.arm
	.equ	NR_MMAP2, 192
	.equ	NR_WRITE, 4
	.equ	NR_EXIT,  1

	@ ---- 段拷贝宏（src 符号, 目标地址, 字数）----
	.macro COPY src, dst, words
	ldr	r1, =\src
	ldr	r3, =\dst
	mov	r2, #\words
1:
	ldr	r4, [r1], #4
	str	r4, [r3], #4
	subs	r2, r2, #1
	bne	1b
	.endm

	.text
	.global _start
_start:
	ldr	sp, =stack_top

	@ ---- mmap2(0x80000000, 0x100000, RWX, FIXED|PRIV|ANON, -1, 0) ----
	ldr	r0, =0x80000000
	ldr	r1, =0x100000
	mov	r2, #7
	ldr	r3, =0x32
	mvn	r4, #0
	mov	r5, #0
	mov	r7, #NR_MMAP2
	svc	#0
	ldr	r6, =0x80000000
	cmp	r0, r6
	bne	L_fail

	@ ---- 载入三段真字节 ----
	COPY	norm_seg,  0x80051090, 212
	COPY	i1500_seg, 0x80011500, 36
	COPY	wrap_seg,  0x8004cc00, 128

	@ ---- 写入 5 个桩 ----
	COPY	stub_log,   0x80046484, W_LOG
	COPY	stub_lock,  0x800d69cc, W_LOCK
	COPY	stub_wslot, 0x80064f0c, W_WSLOT
	COPY	stub_apply, 0x80051ab8, W_APPLY
	COPY	stub_send,  0x800d6b20, W_SEND

	@ ---- 用例循环 ----
	ldr	r4, =cases
	ldr	r5, =results
	ldr	r8, =casecount
	ldr	r8, [r8]
L_cases:
	ldr	r0, [r4], #4		@ id
	ldr	r10, [r4], #4		@ val
	str	r0, [r5]		@ results.id
	ldr	r6, =valbuf
	str	r10, [r6]		@ valbuf = val
	ldr	r3, =0x80090000
	ldr	r10, [r3]
	str	r10, [r5, #8]		@ before
	mov	r1, r6			@ &valbuf
	mov	r2, #4			@ sz
	ldr	r3, =0x8004ccf4
	blx	r3
	str	r0, [r5, #4]		@ ret
	ldr	r3, =0x80090000
	ldr	r10, [r3]
	str	r10, [r5, #12]		@ after
	add	r5, r5, #16
	subs	r8, r8, #1
	bne	L_cases

	@ ---- 组装输出 ----
	ldr	r0, =casecount
	ldr	r0, [r0]		@ ncase
	ldr	r1, =outbuf
	str	r0, [r1]		@ [0] = ncase
	ldr	r2, =results
	add	r3, r1, #4
	mov	r4, r0
	lsl	r4, r4, #4		@ ncase*16 字节
L_oc1:
	ldr	r5, [r2], #4
	str	r5, [r3], #4
	subs	r4, r4, #4
	bne	L_oc1
	ldr	r6, =0x80090000
	ldr	r6, [r6]		@ nevent
	str	r6, [r3], #4
	mov	r4, r6
	lsl	r4, r4, #4
	cmp	r4, #0
	beq	L_oc2d
	ldr	r2, =0x80090004
L_oc2:
	ldr	r5, [r2], #4
	str	r5, [r3], #4
	subs	r4, r4, #4
	bne	L_oc2
L_oc2d:
	@ write(1, outbuf, 4+N+4+nevent*16)
	mov	r0, #1
	ldr	r1, =outbuf
	ldr	r2, =casecount
	ldr	r2, [r2]
	lsl	r2, r2, #4
	add	r2, r2, #8
	ldr	r6, =0x80090000
	ldr	r6, [r6]
	lsl	r6, r6, #4
	add	r2, r2, r6
	mov	r7, #NR_WRITE
	svc	#0
	mov	r0, #0
	mov	r7, #NR_EXIT
	svc	#0

L_fail:
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

@ ============================ 桩（拷贝到目标地址执行） ============================

	.align 4
stub_log:
	movw	r2, #0x0000
	movt	r2, #0x8009
	ldr	r3, [r2]
	add	r3, r3, #1
	str	r3, [r2]
	sub	r3, r3, #1
	lsl	r3, r3, #4
	add	r3, r3, #4
	add	r3, r2, r3
	mov	r12, #4
	str	r12, [r3]
	bx	lr
stub_log_end:

	.align 4
stub_lock:
	movw	r0, #0xab20
	movt	r0, #0x8142
	bx	lr
stub_lock_end:

	.align 4
stub_wslot:
	movw	r2, #0x0000
	movt	r2, #0x8009
	ldr	r3, [r2]
	add	r3, r3, #1
	str	r3, [r2]
	sub	r3, r3, #1
	lsl	r3, r3, #4
	add	r3, r3, #4
	add	r3, r2, r3
	mov	r12, #1
	str	r12, [r3]
	str	r0, [r3, #4]		@ slot
	str	r1, [r3, #8]		@ val
	mov	r0, #0
	bx	lr
stub_wslot_end:

	.align 4
stub_apply:
	movw	r2, #0x0000
	movt	r2, #0x8009
	ldr	r3, [r2]
	add	r3, r3, #1
	str	r3, [r2]
	sub	r3, r3, #1
	lsl	r3, r3, #4
	add	r3, r3, #4
	add	r3, r2, r3
	mov	r12, #2
	str	r12, [r3]
	mov	r0, #0
	bx	lr
stub_apply_end:

	.align 4
stub_send:
	push	{r4, r5}
	movw	r4, #0x0000
	movt	r4, #0x8009
	ldr	r5, [r4]
	add	r5, r5, #1
	str	r5, [r4]
	sub	r5, r5, #1
	lsl	r5, r5, #4
	add	r5, r5, #4
	add	r5, r4, r5
	mov	r12, #3
	str	r12, [r5]
	str	r1, [r5, #4]		@ id
	ldr	r12, [r2]
	str	r12, [r5, #8]		@ val = *ptr
	str	r0, [r5, #12]		@ obj
	pop	{r4, r5}
	mov	r0, #0
	bx	lr
stub_send_end:

	.equ	W_LOG,   (stub_log_end   - stub_log)/4
	.equ	W_LOCK,  (stub_lock_end  - stub_lock)/4
	.equ	W_WSLOT, (stub_wslot_end - stub_wslot)/4
	.equ	W_APPLY, (stub_apply_end - stub_apply)/4
	.equ	W_SEND,  (stub_send_end  - stub_send)/4

@ ============================ 数据 ============================
	.section .rodata
	.align 4
norm_seg:
	.incbin "seg_norm.bin"
	.align 4
i1500_seg:
	.incbin "seg_11500.bin"
	.align 4
wrap_seg:
	.incbin "seg_wrap.bin"

	.align 4
failmsg:
	.ascii "MMAPFAIL"

	.align 4
cases:
	.word	0x134, 106
	.word	0x135, 97
	.word	0x136, 107
	.word	0x137, 14
	.word	0x138, 13
	.word	0x139, 10
	.word	0x13a, 12
	.word	0x13b, 0
	.word	0x110, 0x003FD80A
	.word	0x100, 0x12345678
	.word	0x130, 0x00000ABC
	.word	0x12f, 0
	.word	0x13c, 0
cases_end:
casecount:
	.word	(cases_end - cases) / 8

	.section .bss
	.align 4
valbuf:		.skip 8
results:	.skip 16 * 16
outbuf:		.skip 1600
stack:		.skip 8192
stack_top:
