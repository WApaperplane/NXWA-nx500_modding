@ =============================================================================
@ blk2.s —— A2 特判块（"档位池直写 + 应用触发"）× p7
@ =============================================================================
@ 挂载点：0x4ccf4 (外部变量写包装) 的 "bl 0xd6b20" (0x4cd30) 改道至本块。
@ 调用现场：r0 = 0x8142ab20（全局对象，0x4ccf4 经 0xd69cc 取得）
@           r1 = conv（归一化输出 id）
@           r2 = &val（4 字节值指针）
@           r3 = sz
@ 协议（外部 → 归一化放行 0x130..0x13B → 本块分流）：
@   0x134..0x13A ↔ 槽 0xdc..0xe2（R,G,B,HUE,SAT,SHARP,CON；写入原始值）
@   0x13B = 提交：先写 槽0xda=10（自定义1）→ bl 0x51ab8（读槽→编码→发送 ISP）
@   其余 id（含 0x100..0x12e 等老功能）→ 原样尾调 0xd6b20（透传，无损）
@ 构建：arm-linux-gnueabihf-as + ld -Ttext=0x80011530（见 build_a2_blk.sh）
@ =============================================================================

	.arch armv7-a
	.arm
	.text
	.global _start
	.equ	WRITE_SLOT, 0x80064f0c      @ FUN_00064f0c(slot, val): *0x61aec(slot)=val
	.equ	APPLY_ALL,  0x80051ab8      @ FUN_00051ab8: 读9槽→编码→d6b20×8（自包含）
	.equ	SEND_VAR,   0x800d6b20      @ 原路（变量发送器）

_start:
	push	{r4, r5, r6, lr}
	sub	r4, r1, #0x134              @ r4 = id - 0x134（unsigned 回绕安全）
	cmp	r4, #6
	bls	L_slot                      @ 0x134..0x13A → 7 维直写
	cmp	r4, #7
	beq	L_commit                    @ 0x13B → 提交
	@ else: 透传
	pop	{r4, r5, r6, lr}
	b	SEND_VAR

L_slot:
	ldr	r5, [r2]                    @ val
	add	r0, r4, #0xdc               @ slot = 0xdc + (id-0x134)
	mov	r1, r5
	bl	WRITE_SLOT                  @ 写槽
	mov	r0, #0
	pop	{r4, r5, r6, pc}

L_commit:
	mov	r0, #0xda                   @ 槽 0xda = 10（0x140009 = 自定义1）
	mov	r1, #10
	bl	WRITE_SLOT
	bl	APPLY_ALL                   @ ★ 全链应用（读槽→编码→发送）
	mov	r0, #0
	pop	{r4, r5, r6, pc}
