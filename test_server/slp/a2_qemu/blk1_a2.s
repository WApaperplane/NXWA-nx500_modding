@ blk1_a2.s —— A1 特判块的 A2 改扩版（cmp #3 → cmp #0xB：放行 0x130..0x13B）
@ 放置：0x80011504（与原 A1 块同址）；原 24B：sub/cmp/bhi/str/mov/b
	.arch armv7-a
	.arm
	.text
	.global _start
_start:
	sub	r3, r0, #0x130
	cmp	r3, #0xB
	bhi	0x80051394
	str	r0, [r1]
	mov	r0, #0
	b	0x8005117c
