/* ===== d5_ep_nog_set_bypass @ 0x00011f10  size=36  ARM ===== */
  00011f10:  push       {fp, lr}
  00011f14:  add        fp, sp, #4
  00011f18:  sub        sp, sp, #8
  00011f1c:  str        r0, [fp, #-8]
  00011f20:  bl         #0x83c0   // ->@plt _udd_ep_nog_reg_struct_init
  00011f24:  ldr        r0, [fp, #-8]
  00011f28:  bl         #0x8504   // ->@plt _udd_ep_nog_set_bypass
  00011f2c:  sub        sp, fp, #4
  00011f30:  pop        {fp, pc}

/* ===== d5_ep_nog_set_noisegen @ 0x00011f34  size=240  ARM ===== */
  00011f34:  push       {fp, lr}
  00011f38:  add        fp, sp, #4
  00011f3c:  sub        sp, sp, #0x10
  00011f40:  str        r0, [fp, #-0x10]
  00011f44:  mov        r3, #0
  00011f48:  str        r3, [fp, #-8]
  00011f4c:  bl         #0x83c0   // ->@plt _udd_ep_nog_reg_struct_init
  00011f50:  ldr        r3, [fp, #-0x10]
  00011f54:  ldr        r3, [r3, #8]
  00011f58:  mov        r0, r3
  00011f5c:  bl         #0x89e4   // ->@plt _udd_ep_nog_set_random_seed
  00011f60:  mov        r3, r0
  00011f64:  ldr        r2, [fp, #-8]
  00011f68:  orr        r3, r2, r3
  00011f6c:  str        r3, [fp, #-8]
  00011f70:  ldr        r3, [fp, #-0x10]
  00011f74:  ldr        r2, [r3, #0x10]
  00011f78:  ldr        r3, [fp, #-0x10]
  00011f7c:  ldr        r3, [r3, #8]
  00011f80:  mov        r0, r2
  00011f84:  mov        r1, r3
  00011f88:  bl         #0x8234   // ->@plt _udd_ep_nog_select_rv_type
  00011f8c:  ldr        r3, [fp, #-0x10]
  00011f90:  ldrb       r2, [r3]
  00011f94:  ldr        r3, [fp, #-0x10]
  00011f98:  ldr        r3, [r3, #8]
  00011f9c:  mov        r0, r2
  00011fa0:  mov        r1, r3
  00011fa4:  bl         #0x836c   // ->@plt _udd_ep_nog_set_std_sigma
  00011fa8:  mov        r3, r0
  00011fac:  ldr        r2, [fp, #-8]
  00011fb0:  orr        r3, r2, r3
  00011fb4:  str        r3, [fp, #-8]
  00011fb8:  ldr        r3, [fp, #-0x10]
  00011fbc:  ldr        r2, [r3, #4]
  00011fc0:  ldr        r3, [fp, #-0x10]
  00011fc4:  ldr        r3, [r3, #8]
  00011fc8:  mov        r0, r2
  00011fcc:  mov        r1, r3
  00011fd0:  bl         #0x8474   // ->@plt _udd_ep_nog_set_gamma
  00011fd4:  mov        r3, r0
  00011fd8:  ldr        r2, [fp, #-8]
  00011fdc:  orr        r3, r2, r3
  00011fe0:  str        r3, [fp, #-8]
  00011fe4:  ldr        r3, [fp, #-0x10]
  00011fe8:  ldr        r2, [r3, #0xc]
  00011fec:  ldr        r3, [fp, #-0x10]
  00011ff0:  ldr        r3, [r3, #8]
  00011ff4:  mov        r0, r2
  00011ff8:  mov        r1, r3
  00011ffc:  bl         #0x83d8   // ->@plt _udd_ep_nog_seed_load_switch
  00012000:  ldr        r3, [fp, #-8]
  00012004:  cmp        r3, #0
  00012008:  beq        #0x12014
  0001200c:  mvn        r3, #0
  00012010:  b          #0x12018
  00012014:  mov        r3, #0
  00012018:  mov        r0, r3
  0001201c:  sub        sp, fp, #4
  00012020:  pop        {fp, pc}

/* ===== _udd_ep_mux_nog_rdxi @ 0x0001b7ec  size=580  ARM ===== */
  0001b7ec:  push       {r4, fp, lr}
  0001b7f0:  add        fp, sp, #8
  0001b7f4:  sub        sp, sp, #0x1c
  0001b7f8:  str        r0, [fp, #-0x20]
  0001b7fc:  str        r1, [fp, #-0x24]
  0001b800:  ldr        r4, [pc, #0x208]
  0001b804:  add        r4, pc, r4
  0001b808:  mvn        r3, #0
  0001b80c:  str        r3, [fp, #-0x10]
  0001b810:  ldr        r3, [fp, #-0x24]
  0001b814:  cmp        r3, #0
  0001b818:  bne        #0x1b824
  0001b81c:  movw       r3, #0x1108
  0001b820:  b          #0x1b828
  0001b824:  movw       r3, #0x1208
  0001b828:  str        r3, [fp, #-0x14]
  0001b82c:  ldr        r3, [pc, #0x1e0]
  0001b830:  ldr        r3, [r4, r3]
  0001b834:  ldr        r2, [r3]
  0001b838:  ldr        r3, [fp, #-0x14]
  0001b83c:  add        r3, r2, r3
  0001b840:  ldr        r3, [r3]
  0001b844:  str        r3, [fp, #-0x18]
  0001b848:  ldr        r3, [fp, #-0x20]
  0001b84c:  sub        r3, r3, #1
  0001b850:  cmp        r3, #0xf
  0001b854:  addls      pc, pc, r3, lsl #2
  0001b858:  b          #0x1b9b8
  0001b85c:  b          #0x1b89c
  0001b860:  b          #0x1b89c
  0001b864:  b          #0x1b89c
  0001b868:  b          #0x1b89c
  0001b86c:  b          #0x1b89c
  0001b870:  b          #0x1b8c4
  0001b874:  b          #0x1b8c4
  0001b878:  b          #0x1b8c4
  0001b87c:  b          #0x1b8c4
  0001b880:  b          #0x1b9b8
  0001b884:  b          #0x1b9b8
  0001b888:  b          #0x1b9b8
  0001b88c:  b          #0x1b9b8
  0001b890:  b          #0x1b9b8
  0001b894:  b          #0x1b9b8
  0001b898:  b          #0x1b94c
  0001b89c:  ldr        r3, [fp, #-0x20]
  0001b8a0:  uxtb       r3, r3
  0001b8a4:  and        r3, r3, #0xf
  0001b8a8:  uxtb       r2, r3
  0001b8ac:  ldr        r3, [fp, #-0x18]
  0001b8b0:  bfi        r3, r2, #0x18, #4
  0001b8b4:  str        r3, [fp, #-0x18]
  0001b8b8:  mov        r3, #0xa
  0001b8bc:  str        r3, [fp, #-0x10]
  0001b8c0:  b          #0x1b9e4
  0001b8c4:  ldr        r3, [fp, #-0x20]
  0001b8c8:  sub        r3, r3, #6
  0001b8cc:  mov        r0, r3
  0001b8d0:  ldr        r1, [fp, #-0x24]
  0001b8d4:  bl         #0x8348   // ->@plt _udd_ep_rdma_check_empty
  0001b8d8:  mov        r3, r0
  0001b8dc:  cmp        r3, #0
  0001b8e0:  beq        #0x1b910
  0001b8e4:  ldr        r3, [fp, #-0x20]
  0001b8e8:  uxtb       r3, r3
  0001b8ec:  and        r3, r3, #0xf
  0001b8f0:  uxtb       r2, r3
  0001b8f4:  ldr        r3, [fp, #-0x18]
  0001b8f8:  bfi        r3, r2, #0x18, #4
  0001b8fc:  str        r3, [fp, #-0x18]
  0001b900:  ldr        r3, [fp, #-0x20]
  0001b904:  sub        r3, r3, #6
  0001b908:  str        r3, [fp, #-0x10]
  0001b90c:  b          #0x1b9e4
  0001b910:  ldr        r3, [pc, #0x100]
  0001b914:  add        r3, pc, r3
  0001b918:  mov        r2, r3
  0001b91c:  ldr        r3, [fp, #-0x20]
  0001b920:  sub        r3, r3, #6
  0001b924:  mov        r0, r2
  0001b928:  mov        r1, r3
  0001b92c:  ldr        r3, [pc, #0xe8]
  0001b930:  add        r3, pc, r3
  0001b934:  mov        r2, r3
  0001b938:  movw       r3, #0x101
  0001b93c:  bl         #0x8258   // ->@plt printf
  0001b940:  mvn        r3, #0
  0001b944:  str        r3, [fp, #-0x10]
  0001b948:  b          #0x1b9e4
  0001b94c:  ldr        r0, [fp, #-0x24]
  0001b950:  bl         #0x89d8   // ->@plt _udd_ep_rdma_get_empty
  0001b954:  str        r0, [fp, #-0x10]
  0001b958:  ldr        r3, [fp, #-0x10]
  0001b95c:  cmn        r3, #1
  0001b960:  beq        #0x1b98c
  0001b964:  ldr        r3, [fp, #-0x10]
  0001b968:  uxtb       r3, r3
  0001b96c:  add        r3, r3, #6
  0001b970:  uxtb       r3, r3
  0001b974:  and        r3, r3, #0xf
  0001b978:  uxtb       r2, r3
  0001b97c:  ldr        r3, [fp, #-0x18]
  0001b980:  bfi        r3, r2, #0x18, #4
  0001b984:  str        r3, [fp, #-0x18]
  0001b988:  b          #0x1b9e4
  0001b98c:  ldr        r3, [pc, #0x8c]
  0001b990:  add        r3, pc, r3
  0001b994:  mov        r0, r3
  0001b998:  ldr        r3, [pc, #0x84]
  0001b99c:  add        r3, pc, r3
  0001b9a0:  mov        r1, r3
  0001b9a4:  movw       r2, #0x10b
  0001b9a8:  bl         #0x8258   // ->@plt printf
  0001b9ac:  mvn        r3, #0
  0001b9b0:  str        r3, [fp, #-0x10]
  0001b9b4:  b          #0x1b9e4
  0001b9b8:  ldr        r3, [pc, #0x68]
  0001b9bc:  add        r3, pc, r3
  0001b9c0:  mov        r0, r3
  0001b9c4:  ldr        r3, [pc, #0x60]
  0001b9c8:  add        r3, pc, r3
  0001b9cc:  mov        r1, r3
  0001b9d0:  movw       r2, #0x112
  0001b9d4:  bl         #0x8258   // ->@plt printf
  0001b9d8:  mvn        r3, #0
  0001b9dc:  str        r3, [fp, #-0x10]
  0001b9e0:  mov        r0, r0
  0001b9e4:  ldr        r3, [pc, #0x28]
  0001b9e8:  ldr        r3, [r4, r3]
  0001b9ec:  ldr        r2, [r3]
  0001b9f0:  ldr        r3, [fp, #-0x14]
  0001b9f4:  add        r3, r2, r3
  0001b9f8:  ldr        r2, [fp, #-0x18]
  0001b9fc:  str        r2, [r3]
  0001ba00:  ldr        r3, [fp, #-0x10]
  0001ba04:  mov        r0, r3
  0001ba08:  sub        sp, fp, #8
  0001ba0c:  pop        {r4, fp, pc}
  0001ba10:  strheq     lr, [r2], -r4
  0001ba14:  ldrdeq     r0, r1, [r0], -r4
  0001ba18:  strheq     r5, [r2], -ip
  0001ba1c:  andeq      r5, r2, r0, lsl #29
  0001ba20:  andeq      r5, r2, r8, lsl #21
  0001ba24:  andeq      r5, r2, r4, lsl lr
  0001ba28:  andeq      r5, r2, r8, ror sl
  0001ba2c:  andeq      r5, r2, r8, ror #27

/* ===== _udd_ep_mux_nog_wdxi @ 0x0001caf8  size=296  ARM ===== */
  0001caf8:  push       {fp, lr}
  0001cafc:  add        fp, sp, #4
  0001cb00:  sub        sp, sp, #0x10
  0001cb04:  str        r0, [fp, #-0x10]
  0001cb08:  str        r1, [fp, #-0x14]
  0001cb0c:  mvn        r3, #0
  0001cb10:  str        r3, [fp, #-8]
  0001cb14:  ldr        r3, [fp, #-0x10]
  0001cb18:  cmp        r3, #0
  0001cb1c:  blt        #0x1cbf4
  0001cb20:  cmp        r3, #4
  0001cb24:  ble        #0x1cb34
  0001cb28:  cmp        r3, #0x14
  0001cb2c:  beq        #0x1cb98
  0001cb30:  b          #0x1cbf4
  0001cb34:  ldr        r0, [fp, #-0x10]
  0001cb38:  ldr        r1, [fp, #-0x14]
  0001cb3c:  bl         #0x8bdc   // ->@plt _udd_ep_wdma_check_empty
  0001cb40:  mov        r3, r0
  0001cb44:  cmp        r3, #0
  0001cb48:  beq        #0x1cb68
  0001cb4c:  ldr        r0, [fp, #-0x10]
  0001cb50:  mov        r1, #0xa
  0001cb54:  ldr        r2, [fp, #-0x14]
  0001cb58:  bl         #0x8e64   // ->@plt _udd_ep_mux_wdma
  0001cb5c:  ldr        r3, [fp, #-0x10]
  0001cb60:  str        r3, [fp, #-8]
  0001cb64:  b          #0x1cc00
  0001cb68:  ldr        r3, [pc, #0xa0]
  0001cb6c:  add        r3, pc, r3
  0001cb70:  mov        r0, r3
  0001cb74:  ldr        r1, [fp, #-0x10]
  0001cb78:  ldr        r3, [pc, #0x94]
  0001cb7c:  add        r3, pc, r3
  0001cb80:  mov        r2, r3
  0001cb84:  movw       r3, #0x2d1
  0001cb88:  bl         #0x8258   // ->@plt printf
  0001cb8c:  mvn        r3, #0
  0001cb90:  str        r3, [fp, #-8]
  0001cb94:  b          #0x1cc00
  0001cb98:  ldr        r0, [fp, #-0x14]
  0001cb9c:  bl         #0x8d74   // ->@plt _udd_ep_wdma_get_empty
  0001cba0:  str        r0, [fp, #-8]
  0001cba4:  ldr        r3, [fp, #-8]
  0001cba8:  cmn        r3, #1
  0001cbac:  beq        #0x1cbc4
  0001cbb0:  ldr        r0, [fp, #-8]
  0001cbb4:  mov        r1, #0xa
  0001cbb8:  ldr        r2, [fp, #-0x14]
  0001cbbc:  bl         #0x8e64   // ->@plt _udd_ep_mux_wdma
  0001cbc0:  b          #0x1cc00
  0001cbc4:  ldr        r3, [pc, #0x4c]
  0001cbc8:  add        r3, pc, r3
  0001cbcc:  mov        r0, r3
  0001cbd0:  ldr        r1, [fp, #-0x10]
  0001cbd4:  ldr        r3, [pc, #0x40]
  0001cbd8:  add        r3, pc, r3
  0001cbdc:  mov        r2, r3
  0001cbe0:  movw       r3, #0x2da
  0001cbe4:  bl         #0x8258   // ->@plt printf
  0001cbe8:  mvn        r3, #0
  0001cbec:  str        r3, [fp, #-8]
  0001cbf0:  b          #0x1cc00
  0001cbf4:  mvn        r3, #0
  0001cbf8:  str        r3, [fp, #-8]
  0001cbfc:  mov        r0, r0
  0001cc00:  ldr        r3, [fp, #-8]
  0001cc04:  mov        r0, r3
  0001cc08:  sub        sp, fp, #4
  0001cc0c:  pop        {fp, pc}
  0001cc10:  andeq      r4, r2, r0, lsl sb
  0001cc14:  andeq      r4, r2, ip, asr fp
  0001cc18:  strheq     r4, [r2], -r4
  0001cc1c:  andeq      r4, r2, r0, lsl #22

/* ===== _udd_ep_demux_nog_rdxi @ 0x0001dc18  size=140  ARM ===== */
  0001dc18:  str        fp, [sp, #-4]!
  0001dc1c:  add        fp, sp, #0
  0001dc20:  sub        sp, sp, #0x14
  0001dc24:  str        r0, [fp, #-0x10]
  0001dc28:  ldr        r2, [pc, #0x6c]
  0001dc2c:  add        r2, pc, r2
  0001dc30:  ldr        r3, [fp, #-0x10]
  0001dc34:  cmp        r3, #0
  0001dc38:  bne        #0x1dc44
  0001dc3c:  movw       r3, #0x1108
  0001dc40:  b          #0x1dc48
  0001dc44:  movw       r3, #0x1208
  0001dc48:  str        r3, [fp, #-8]
  0001dc4c:  ldr        r3, [pc, #0x4c]
  0001dc50:  ldr        r3, [r2, r3]
  0001dc54:  ldr        r1, [r3]
  0001dc58:  ldr        r3, [fp, #-8]
  0001dc5c:  add        r3, r1, r3
  0001dc60:  ldr        r3, [r3]
  0001dc64:  str        r3, [fp, #-0xc]
  0001dc68:  ldr        r3, [fp, #-0xc]
  0001dc6c:  orr        r3, r3, #0xf000000
  0001dc70:  str        r3, [fp, #-0xc]
  0001dc74:  ldr        r3, [pc, #0x24]
  0001dc78:  ldr        r3, [r2, r3]
  0001dc7c:  ldr        r2, [r3]
  0001dc80:  ldr        r3, [fp, #-8]
  0001dc84:  add        r3, r2, r3
  0001dc88:  ldr        r2, [fp, #-0xc]
  0001dc8c:  str        r2, [r3]
  0001dc90:  add        sp, fp, #0
  0001dc94:  ldm        sp!, {fp}
  0001dc98:  bx         lr
  0001dc9c:  andeq      ip, r2, ip, lsl #13
  0001dca0:  ldrdeq     r0, r1, [r0], -r4

/* ===== _udd_ep_demux_nog_wdxi @ 0x0001e5a4  size=288  ARM ===== */
  0001e5a4:  str        fp, [sp, #-4]!
  0001e5a8:  add        fp, sp, #0
  0001e5ac:  sub        sp, sp, #0x1c
  0001e5b0:  str        r0, [fp, #-0x18]
  0001e5b4:  ldr        r3, [pc, #0x100]
  0001e5b8:  add        r3, pc, r3
  0001e5bc:  ldr        r2, [fp, #-0x18]
  0001e5c0:  cmp        r2, #0
  0001e5c4:  bne        #0x1e5d0
  0001e5c8:  movw       r2, #0x110c
  0001e5cc:  b          #0x1e5d4
  0001e5d0:  movw       r2, #0x120c
  0001e5d4:  str        r2, [fp, #-0xc]
  0001e5d8:  ldr        r2, [pc, #0xe0]
  0001e5dc:  ldr        r2, [r3, r2]
  0001e5e0:  ldr        r1, [r2]
  0001e5e4:  ldr        r2, [fp, #-0xc]
  0001e5e8:  add        r2, r1, r2
  0001e5ec:  ldr        r2, [r2]
  0001e5f0:  str        r2, [fp, #-0x14]
  0001e5f4:  mov        r2, #0
  0001e5f8:  str        r2, [fp, #-8]
  0001e5fc:  b          #0x1e630
  0001e600:  ldr        r1, [fp, #-0x14]
  0001e604:  ldr        r2, [fp, #-8]
  0001e608:  lsl        r2, r2, #2
  0001e60c:  lsr        r2, r1, r2
  0001e610:  and        r2, r2, #0xf
  0001e614:  str        r2, [fp, #-0x10]
  0001e618:  ldr        r2, [fp, #-0x10]
  0001e61c:  cmp        r2, #0xa
  0001e620:  beq        #0x1e640
  0001e624:  ldr        r2, [fp, #-8]
  0001e628:  add        r2, r2, #1
  0001e62c:  str        r2, [fp, #-8]
  0001e630:  ldr        r2, [fp, #-8]
  0001e634:  cmp        r2, #4
  0001e638:  bls        #0x1e600
  0001e63c:  b          #0x1e644
  0001e640:  mov        r0, r0
  0001e644:  ldr        r2, [fp, #-8]
  0001e648:  cmp        r2, #5
  0001e64c:  beq        #0x1e6ac
  0001e650:  ldr        r1, [fp, #-0x14]
  0001e654:  ldr        r2, [fp, #-8]
  0001e658:  lsl        r2, r2, #2
  0001e65c:  mov        r0, #0xf
  0001e660:  lsl        r2, r0, r2
  0001e664:  mvn        r2, r2
  0001e668:  and        r2, r1, r2
  0001e66c:  str        r2, [fp, #-0x14]
  0001e670:  ldr        r1, [fp, #-0x14]
  0001e674:  ldr        r2, [fp, #-8]
  0001e678:  lsl        r2, r2, #2
  0001e67c:  mov        r0, #0xf
  0001e680:  lsl        r2, r0, r2
  0001e684:  orr        r2, r1, r2
  0001e688:  str        r2, [fp, #-0x14]
  0001e68c:  ldr        r2, [pc, #0x2c]
  0001e690:  ldr        r3, [r3, r2]
  0001e694:  ldr        r2, [r3]
  0001e698:  ldr        r3, [fp, #-0xc]
  0001e69c:  add        r3, r2, r3
  0001e6a0:  ldr        r2, [fp, #-0x14]
  0001e6a4:  str        r2, [r3]
  0001e6a8:  b          #0x1e6b0
  0001e6ac:  mov        r0, r0
  0001e6b0:  add        sp, fp, #0
  0001e6b4:  ldm        sp!, {fp}
  0001e6b8:  bx         lr
  0001e6bc:  andeq      fp, r2, r0, lsl #26
  0001e6c0:  ldrdeq     r0, r1, [r0], -r4

/* ===== _udd_ep_nog_reg_struct_init @ 0x00024ec4  size=248  ARM ===== */
  00024ec4:  str        fp, [sp, #-4]!
  00024ec8:  add        fp, sp, #0
  00024ecc:  ldr        r2, [pc, #0xdc]
  00024ed0:  add        r2, pc, r2
  00024ed4:  ldr        r3, [pc, #0xd8]
  00024ed8:  ldr        r3, [r2, r3]
  00024edc:  mov        r1, #0
  00024ee0:  str        r1, [r3]
  00024ee4:  add        r3, r3, #4
  00024ee8:  mov        r1, #0
  00024eec:  str        r1, [r3]
  00024ef0:  add        r3, r3, #4
  00024ef4:  mov        r1, #0
  00024ef8:  str        r1, [r3]
  00024efc:  add        r3, r3, #4
  00024f00:  mov        r1, #0
  00024f04:  str        r1, [r3]
  00024f08:  add        r3, r3, #4
  00024f0c:  mov        r1, #0
  00024f10:  str        r1, [r3]
  00024f14:  add        r3, r3, #4
  00024f18:  mov        r1, #0
  00024f1c:  str        r1, [r3]
  00024f20:  add        r3, r3, #4
  00024f24:  mov        r1, #0
  00024f28:  str        r1, [r3]
  00024f2c:  add        r3, r3, #4
  00024f30:  mov        r1, #0
  00024f34:  str        r1, [r3]
  00024f38:  add        r3, r3, #4
  00024f3c:  ldr        r3, [pc, #0x74]
  00024f40:  ldr        r3, [r2, r3]
  00024f44:  mov        r2, #0
  00024f48:  str        r2, [r3]
  00024f4c:  add        r3, r3, #4
  00024f50:  mov        r2, #0
  00024f54:  str        r2, [r3]
  00024f58:  add        r3, r3, #4
  00024f5c:  mov        r2, #0
  00024f60:  str        r2, [r3]
  00024f64:  add        r3, r3, #4
  00024f68:  mov        r2, #0
  00024f6c:  str        r2, [r3]
  00024f70:  add        r3, r3, #4
  00024f74:  mov        r2, #0
  00024f78:  str        r2, [r3]
  00024f7c:  add        r3, r3, #4
  00024f80:  mov        r2, #0
  00024f84:  str        r2, [r3]
  00024f88:  add        r3, r3, #4
  00024f8c:  mov        r2, #0
  00024f90:  str        r2, [r3]
  00024f94:  add        r3, r3, #4
  00024f98:  mov        r2, #0
  00024f9c:  str        r2, [r3]
  00024fa0:  add        r3, r3, #4
  00024fa4:  add        sp, fp, #0
  00024fa8:  ldm        sp!, {fp}
  00024fac:  bx         lr
  00024fb0:  andeq      r5, r2, r8, ror #7
  00024fb4:  andeq      r0, r0, r8, lsr r5
  00024fb8:  strdeq     r0, r1, [r0], -ip

/* ===== _udd_ep_nog_set_random_seed @ 0x00024fbc  size=232  ARM ===== */
  00024fbc:  str        fp, [sp, #-4]!
  00024fc0:  add        fp, sp, #0
  00024fc4:  sub        sp, sp, #0x14
  00024fc8:  str        r0, [fp, #-0x10]
  00024fcc:  ldr        r3, [pc, #0xc0]
  00024fd0:  add        r3, pc, r3
  00024fd4:  ldr        r2, [fp, #-0x10]
  00024fd8:  cmp        r2, #0
  00024fdc:  bne        #0x24ff8
  00024fe0:  ldr        r2, [pc, #0xb0]
  00024fe4:  ldr        r2, [r3, r2]
  00024fe8:  str        r2, [fp, #-8]
  00024fec:  mov        r2, #0
  00024ff0:  str        r2, [fp, #-0xc]
  00024ff4:  b          #0x2500c
  00024ff8:  ldr        r2, [pc, #0x9c]
  00024ffc:  ldr        r2, [r3, r2]
  00025000:  str        r2, [fp, #-8]
  00025004:  mov        r2, #0x30
  00025008:  str        r2, [fp, #-0xc]
  0002500c:  ldr        r0, [fp, #-8]
  00025010:  ldr        r2, [r0, #8]
  00025014:  movw       r1, #0xabcd
  00025018:  movt       r1, #0x1234
  0002501c:  bfi        r2, r1, #0, #0x20
  00025020:  str        r2, [r0, #8]
  00025024:  ldr        r2, [pc, #0x74]
  00025028:  ldr        r2, [r3, r2]
  0002502c:  ldr        r1, [r2]
  00025030:  ldr        r2, [fp, #-0xc]
  00025034:  add        r2, r1, r2
  00025038:  add        r2, r2, #8
  0002503c:  ldr        r1, [fp, #-8]
  00025040:  ldr        r1, [r1, #8]
  00025044:  str        r1, [r2]
  00025048:  ldr        r1, [fp, #-8]
  0002504c:  ldr        r2, [r1, #0xc]
  00025050:  movw       r0, #0x1234
  00025054:  bfi        r2, r0, #0, #0x20
  00025058:  str        r2, [r1, #0xc]
  0002505c:  ldr        r2, [pc, #0x3c]
  00025060:  ldr        r3, [r3, r2]
  00025064:  ldr        r2, [r3]
  00025068:  ldr        r3, [fp, #-0xc]
  0002506c:  add        r3, r2, r3
  00025070:  add        r3, r3, #0xc
  00025074:  ldr        r2, [fp, #-8]
  00025078:  ldr        r2, [r2, #0xc]
  0002507c:  str        r2, [r3]
  00025080:  mov        r3, #0
  00025084:  mov        r0, r3
  00025088:  add        sp, fp, #0
  0002508c:  ldm        sp!, {fp}
  00025090:  bx         lr
  00025094:  andeq      r5, r2, r8, ror #5
  00025098:  andeq      r0, r0, r8, lsr r5
  0002509c:  strdeq     r0, r1, [r0], -ip
  000250a0:  andeq      r0, r0, r0, ror #9

/* ===== _udd_ep_nog_seed_load_switch @ 0x000250a4  size=176  ARM ===== */
  000250a4:  str        fp, [sp, #-4]!
  000250a8:  add        fp, sp, #0
  000250ac:  sub        sp, sp, #0x14
  000250b0:  str        r0, [fp, #-0x10]
  000250b4:  str        r1, [fp, #-0x14]
  000250b8:  ldr        r3, [pc, #0x84]
  000250bc:  add        r3, pc, r3
  000250c0:  ldr        r2, [fp, #-0x14]
  000250c4:  cmp        r2, #0
  000250c8:  bne        #0x250e4
  000250cc:  ldr        r2, [pc, #0x74]
  000250d0:  ldr        r2, [r3, r2]
  000250d4:  str        r2, [fp, #-8]
  000250d8:  mov        r2, #0
  000250dc:  str        r2, [fp, #-0xc]
  000250e0:  b          #0x250f8
  000250e4:  ldr        r2, [pc, #0x60]
  000250e8:  ldr        r2, [r3, r2]
  000250ec:  str        r2, [fp, #-8]
  000250f0:  mov        r2, #0x30
  000250f4:  str        r2, [fp, #-0xc]
  000250f8:  ldr        r2, [fp, #-0x10]
  000250fc:  uxtb       r2, r2
  00025100:  and        r2, r2, #1
  00025104:  uxtb       r0, r2
  00025108:  ldr        r1, [fp, #-8]
  0002510c:  ldrb       r2, [r1]
  00025110:  bfi        r2, r0, #1, #1
  00025114:  strb       r2, [r1]
  00025118:  ldr        r2, [pc, #0x30]
  0002511c:  ldr        r3, [r3, r2]
  00025120:  ldr        r2, [r3]
  00025124:  ldr        r3, [fp, #-0xc]
  00025128:  add        r3, r2, r3
  0002512c:  ldr        r2, [fp, #-8]
  00025130:  ldr        r2, [r2]
  00025134:  str        r2, [r3]
  00025138:  add        sp, fp, #0
  0002513c:  ldm        sp!, {fp}
  00025140:  bx         lr
  00025144:  strdeq     r5, r6, [r2], -ip
  00025148:  andeq      r0, r0, r8, lsr r5
  0002514c:  strdeq     r0, r1, [r0], -ip
  00025150:  andeq      r0, r0, r0, ror #9

/* ===== _udd_ep_nog_select_rv_type @ 0x00025154  size=176  ARM ===== */
  00025154:  str        fp, [sp, #-4]!
  00025158:  add        fp, sp, #0
  0002515c:  sub        sp, sp, #0x14
  00025160:  str        r0, [fp, #-0x10]
  00025164:  str        r1, [fp, #-0x14]
  00025168:  ldr        r3, [pc, #0x84]
  0002516c:  add        r3, pc, r3
  00025170:  ldr        r2, [fp, #-0x14]
  00025174:  cmp        r2, #0
  00025178:  bne        #0x25194
  0002517c:  ldr        r2, [pc, #0x74]
  00025180:  ldr        r2, [r3, r2]
  00025184:  str        r2, [fp, #-8]
  00025188:  mov        r2, #0
  0002518c:  str        r2, [fp, #-0xc]
  00025190:  b          #0x251a8
  00025194:  ldr        r2, [pc, #0x60]
  00025198:  ldr        r2, [r3, r2]
  0002519c:  str        r2, [fp, #-8]
  000251a0:  mov        r2, #0x30
  000251a4:  str        r2, [fp, #-0xc]
  000251a8:  ldr        r2, [fp, #-0x10]
  000251ac:  uxtb       r2, r2
  000251b0:  and        r2, r2, #1
  000251b4:  uxtb       r0, r2
  000251b8:  ldr        r1, [fp, #-8]
  000251bc:  ldrb       r2, [r1]
  000251c0:  bfi        r2, r0, #0, #1
  000251c4:  strb       r2, [r1]
  000251c8:  ldr        r2, [pc, #0x30]
  000251cc:  ldr        r3, [r3, r2]
  000251d0:  ldr        r2, [r3]
  000251d4:  ldr        r3, [fp, #-0xc]
  000251d8:  add        r3, r2, r3
  000251dc:  ldr        r2, [fp, #-8]
  000251e0:  ldr        r2, [r2]
  000251e4:  str        r2, [r3]
  000251e8:  add        sp, fp, #0
  000251ec:  ldm        sp!, {fp}
  000251f0:  bx         lr
  000251f4:  andeq      r5, r2, ip, asr #2
  000251f8:  andeq      r0, r0, r8, lsr r5
  000251fc:  strdeq     r0, r1, [r0], -ip
  00025200:  andeq      r0, r0, r0, ror #9

/* ===== _udd_ep_nog_set_std_sigma @ 0x00025204  size=432  ARM ===== */
  00025204:  push       {r4, fp, lr}
  00025208:  add        fp, sp, #8
  0002520c:  sub        sp, sp, #0x74
  00025210:  mov        r3, r0
  00025214:  str        r1, [fp, #-0x7c]
  00025218:  strb       r3, [fp, #-0x75]
  0002521c:  ldr        r4, [pc, #0x17c]
  00025220:  add        r4, pc, r4
  00025224:  ldr        r3, [pc, #0x178]
  00025228:  add        r3, pc, r3
  0002522c:  sub        r1, fp, #0x74
  00025230:  mov        r2, r3
  00025234:  mov        r3, #0x60
  00025238:  mov        r0, r1
  0002523c:  mov        r1, r2
  00025240:  mov        r2, r3
  00025244:  bl         #0x8330   // ->@plt memcpy
  00025248:  ldr        r3, [fp, #-0x7c]
  0002524c:  cmp        r3, #0
  00025250:  bne        #0x2526c
  00025254:  ldr        r3, [pc, #0x14c]
  00025258:  ldr        r3, [r4, r3]
  0002525c:  str        r3, [fp, #-0x10]
  00025260:  mov        r3, #0
  00025264:  str        r3, [fp, #-0x14]
  00025268:  b          #0x25280
  0002526c:  ldr        r3, [pc, #0x138]
  00025270:  ldr        r3, [r4, r3]
  00025274:  str        r3, [fp, #-0x10]
  00025278:  mov        r3, #0x30
  0002527c:  str        r3, [fp, #-0x14]
  00025280:  ldrb       r3, [fp, #-0x75]
  00025284:  cmp        r3, #0x1f
  00025288:  bls        #0x25294
  0002528c:  mvn        r3, #0
  00025290:  b          #0x25394
  00025294:  ldrb       r3, [fp, #-0x75]
  00025298:  and        r3, r3, #0x1f
  0002529c:  uxtb       r1, r3
  000252a0:  ldr        r2, [fp, #-0x10]
  000252a4:  ldrb       r3, [r2, #2]
  000252a8:  bfi        r3, r1, #0, #5
  000252ac:  strb       r3, [r2, #2]
  000252b0:  ldr        r3, [pc, #0xf8]
  000252b4:  ldr        r3, [r4, r3]
  000252b8:  ldr        r2, [r3]
  000252bc:  ldr        r3, [fp, #-0x14]
  000252c0:  add        r3, r2, r3
  000252c4:  ldr        r2, [fp, #-0x10]
  000252c8:  ldr        r2, [r2]
  000252cc:  str        r2, [r3]
  000252d0:  ldrb       r2, [fp, #-0x75]
  000252d4:  mvn        r1, #0x67
  000252d8:  mov        r3, r2
  000252dc:  lsl        r3, r3, #1
  000252e0:  add        r3, r3, r2
  000252e4:  sub        r2, fp, #0xc
  000252e8:  add        r3, r2, r3
  000252ec:  add        r3, r3, r1
  000252f0:  ldrb       r1, [r3]
  000252f4:  ldr        r2, [fp, #-0x10]
  000252f8:  ldrb       r3, [r2, #4]
  000252fc:  bfi        r3, r1, #0, #8
  00025300:  strb       r3, [r2, #4]
  00025304:  ldrb       r2, [fp, #-0x75]
  00025308:  mvn        r1, #0x66
  0002530c:  mov        r3, r2
  00025310:  lsl        r3, r3, #1
  00025314:  add        r3, r3, r2
  00025318:  sub        r2, fp, #0xc
  0002531c:  add        r3, r2, r3
  00025320:  add        r3, r3, r1
  00025324:  ldrb       r1, [r3]
  00025328:  ldr        r2, [fp, #-0x10]
  0002532c:  ldrb       r3, [r2, #5]
  00025330:  bfi        r3, r1, #0, #8
  00025334:  strb       r3, [r2, #5]
  00025338:  ldrb       r2, [fp, #-0x75]
  0002533c:  mvn        r1, #0x65
  00025340:  mov        r3, r2
  00025344:  lsl        r3, r3, #1
  00025348:  add        r3, r3, r2
  0002534c:  sub        r2, fp, #0xc
  00025350:  add        r3, r2, r3
  00025354:  add        r3, r3, r1
  00025358:  ldrb       r1, [r3]
  0002535c:  ldr        r2, [fp, #-0x10]
  00025360:  ldrb       r3, [r2, #6]
  00025364:  bfi        r3, r1, #0, #8
  00025368:  strb       r3, [r2, #6]
  0002536c:  ldr        r3, [pc, #0x3c]
  00025370:  ldr        r3, [r4, r3]
  00025374:  ldr        r2, [r3]
  00025378:  ldr        r3, [fp, #-0x14]
  0002537c:  add        r3, r2, r3
  00025380:  add        r3, r3, #4
  00025384:  ldr        r2, [fp, #-0x10]
  00025388:  ldr        r2, [r2, #4]
  0002538c:  str        r2, [r3]
  00025390:  mov        r3, #0
  00025394:  mov        r0, r3
  00025398:  sub        sp, fp, #8
  0002539c:  pop        {r4, fp, pc}
  000253a0:  muleq      r2, r8, r0
  000253a4:  andeq      ip, r1, ip, lsr #15
  000253a8:  andeq      r0, r0, r8, lsr r5
  000253ac:  strdeq     r0, r1, [r0], -ip
  000253b0:  andeq      r0, r0, r0, ror #9

/* ===== _udd_ep_nog_set_gamma @ 0x000253b4  size=684  ARM ===== */
  000253b4:  str        fp, [sp, #-4]!
  000253b8:  add        fp, sp, #0
  000253bc:  sub        sp, sp, #0x1c
  000253c0:  str        r0, [fp, #-0x18]
  000253c4:  str        r1, [fp, #-0x1c]
  000253c8:  ldr        r3, [pc, #0x280]
  000253cc:  add        r3, pc, r3
  000253d0:  ldr        r2, [fp, #-0x1c]
  000253d4:  cmp        r2, #0
  000253d8:  bne        #0x253f4
  000253dc:  ldr        r2, [pc, #0x270]
  000253e0:  ldr        r2, [r3, r2]
  000253e4:  str        r2, [fp, #-0xc]
  000253e8:  mov        r2, #0
  000253ec:  str        r2, [fp, #-0x10]
  000253f0:  b          #0x25408
  000253f4:  ldr        r2, [pc, #0x25c]
  000253f8:  ldr        r2, [r3, r2]
  000253fc:  str        r2, [fp, #-0xc]
  00025400:  mov        r2, #0x30
  00025404:  str        r2, [fp, #-0x10]
  00025408:  mov        r2, #0
  0002540c:  str        r2, [fp, #-8]
  00025410:  b          #0x25420
  00025414:  ldr        r2, [fp, #-8]
  00025418:  add        r2, r2, #1
  0002541c:  str        r2, [fp, #-8]
  00025420:  ldr        r2, [fp, #-8]
  00025424:  cmp        r2, #0xf
  00025428:  ble        #0x25414
  0002542c:  ldr        r2, [fp, #-0x18]
  00025430:  ldrb       r0, [r2]
  00025434:  ldr        r1, [fp, #-0xc]
  00025438:  ldrb       r2, [r1, #0x10]
  0002543c:  bfi        r2, r0, #0, #8
  00025440:  strb       r2, [r1, #0x10]
  00025444:  ldr        r2, [fp, #-0x18]
  00025448:  ldrb       r0, [r2, #1]
  0002544c:  ldr        r1, [fp, #-0xc]
  00025450:  ldrb       r2, [r1, #0x11]
  00025454:  bfi        r2, r0, #0, #8
  00025458:  strb       r2, [r1, #0x11]
  0002545c:  ldr        r2, [fp, #-0x18]
  00025460:  ldrb       r0, [r2, #2]
  00025464:  ldr        r1, [fp, #-0xc]
  00025468:  ldrb       r2, [r1, #0x12]
  0002546c:  bfi        r2, r0, #0, #8
  00025470:  strb       r2, [r1, #0x12]
  00025474:  ldr        r2, [fp, #-0x18]
  00025478:  ldrb       r0, [r2, #3]
  0002547c:  ldr        r1, [fp, #-0xc]
  00025480:  ldrb       r2, [r1, #0x13]
  00025484:  bfi        r2, r0, #0, #8
  00025488:  strb       r2, [r1, #0x13]
  0002548c:  ldr        r2, [pc, #0x1c8]
  00025490:  ldr        r2, [r3, r2]
  00025494:  ldr        r1, [r2]
  00025498:  ldr        r2, [fp, #-0x10]
  0002549c:  add        r2, r1, r2
  000254a0:  add        r2, r2, #0x10
  000254a4:  ldr        r1, [fp, #-0xc]
  000254a8:  ldr        r1, [r1, #0x10]
  000254ac:  str        r1, [r2]
  000254b0:  ldr        r2, [fp, #-0x18]
  000254b4:  ldrb       r0, [r2, #4]
  000254b8:  ldr        r1, [fp, #-0xc]
  000254bc:  ldrb       r2, [r1, #0x14]
  000254c0:  bfi        r2, r0, #0, #8
  000254c4:  strb       r2, [r1, #0x14]
  000254c8:  ldr        r2, [fp, #-0x18]
  000254cc:  ldrb       r0, [r2, #5]
  000254d0:  ldr        r1, [fp, #-0xc]
  000254d4:  ldrb       r2, [r1, #0x15]
  000254d8:  bfi        r2, r0, #0, #8
  000254dc:  strb       r2, [r1, #0x15]
  000254e0:  ldr        r2, [fp, #-0x18]
  000254e4:  ldrb       r0, [r2, #6]
  000254e8:  ldr        r1, [fp, #-0xc]
  000254ec:  ldrb       r2, [r1, #0x16]
  000254f0:  bfi        r2, r0, #0, #8
  000254f4:  strb       r2, [r1, #0x16]
  000254f8:  ldr        r2, [fp, #-0x18]
  000254fc:  ldrb       r0, [r2, #7]
  00025500:  ldr        r1, [fp, #-0xc]
  00025504:  ldrb       r2, [r1, #0x17]
  00025508:  bfi        r2, r0, #0, #8
  0002550c:  strb       r2, [r1, #0x17]
  00025510:  ldr        r2, [pc, #0x144]
  00025514:  ldr        r2, [r3, r2]
  00025518:  ldr        r1, [r2]
  0002551c:  ldr        r2, [fp, #-0x10]
  00025520:  add        r2, r1, r2
  00025524:  add        r2, r2, #0x14
  00025528:  ldr        r1, [fp, #-0xc]
  0002552c:  ldr        r1, [r1, #0x14]
  00025530:  str        r1, [r2]
  00025534:  ldr        r2, [fp, #-0x18]
  00025538:  ldrb       r0, [r2, #8]
  0002553c:  ldr        r1, [fp, #-0xc]
  00025540:  ldrb       r2, [r1, #0x18]
  00025544:  bfi        r2, r0, #0, #8
  00025548:  strb       r2, [r1, #0x18]
  0002554c:  ldr        r2, [fp, #-0x18]
  00025550:  ldrb       r0, [r2, #9]
  00025554:  ldr        r1, [fp, #-0xc]
  00025558:  ldrb       r2, [r1, #0x19]
  0002555c:  bfi        r2, r0, #0, #8
  00025560:  strb       r2, [r1, #0x19]
  00025564:  ldr        r2, [fp, #-0x18]
  00025568:  ldrb       r0, [r2, #0xa]
  0002556c:  ldr        r1, [fp, #-0xc]
  00025570:  ldrb       r2, [r1, #0x1a]
  00025574:  bfi        r2, r0, #0, #8
  00025578:  strb       r2, [r1, #0x1a]
  0002557c:  ldr        r2, [fp, #-0x18]
  00025580:  ldrb       r0, [r2, #0xb]
  00025584:  ldr        r1, [fp, #-0xc]
  00025588:  ldrb       r2, [r1, #0x1b]
  0002558c:  bfi        r2, r0, #0, #8
  00025590:  strb       r2, [r1, #0x1b]
  00025594:  ldr        r2, [pc, #0xc0]
  00025598:  ldr        r2, [r3, r2]
  0002559c:  ldr        r1, [r2]
  000255a0:  ldr        r2, [fp, #-0x10]
  000255a4:  add        r2, r1, r2
  000255a8:  add        r2, r2, #0x18
  000255ac:  ldr        r1, [fp, #-0xc]
  000255b0:  ldr        r1, [r1, #0x18]
  000255b4:  str        r1, [r2]
  000255b8:  ldr        r2, [fp, #-0x18]
  000255bc:  ldrb       r0, [r2, #0xc]
  000255c0:  ldr        r1, [fp, #-0xc]
  000255c4:  ldrb       r2, [r1, #0x1c]
  000255c8:  bfi        r2, r0, #0, #8
  000255cc:  strb       r2, [r1, #0x1c]
  000255d0:  ldr        r2, [fp, #-0x18]
  000255d4:  ldrb       r0, [r2, #0xd]
  000255d8:  ldr        r1, [fp, #-0xc]
  000255dc:  ldrb       r2, [r1, #0x1d]
  000255e0:  bfi        r2, r0, #0, #8
  000255e4:  strb       r2, [r1, #0x1d]
  000255e8:  ldr        r2, [fp, #-0x18]
  000255ec:  ldrb       r0, [r2, #0xe]
  000255f0:  ldr        r1, [fp, #-0xc]
  000255f4:  ldrb       r2, [r1, #0x1e]
  000255f8:  bfi        r2, r0, #0, #8
  000255fc:  strb       r2, [r1, #0x1e]
  00025600:  ldr        r2, [fp, #-0x18]
  00025604:  ldrb       r0, [r2, #0xf]
  00025608:  ldr        r1, [fp, #-0xc]
  0002560c:  ldrb       r2, [r1, #0x1f]
  00025610:  bfi        r2, r0, #0, #8
  00025614:  strb       r2, [r1, #0x1f]
  00025618:  ldr        r2, [pc, #0x3c]
  0002561c:  ldr        r3, [r3, r2]
  00025620:  ldr        r2, [r3]
  00025624:  ldr        r3, [fp, #-0x10]
  00025628:  add        r3, r2, r3
  0002562c:  add        r3, r3, #0x1c
  00025630:  ldr        r2, [fp, #-0xc]
  00025634:  ldr        r2, [r2, #0x1c]
  00025638:  str        r2, [r3]
  0002563c:  mov        r3, #0
  00025640:  mov        r0, r3
  00025644:  add        sp, fp, #0
  00025648:  ldm        sp!, {fp}
  0002564c:  bx         lr
  00025650:  andeq      r4, r2, ip, ror #29
  00025654:  andeq      r0, r0, r8, lsr r5
  00025658:  strdeq     r0, r1, [r0], -ip
  0002565c:  andeq      r0, r0, r0, ror #9

/* ===== _udd_ep_nog_set_bypass @ 0x00025660  size=240  ARM ===== */
  00025660:  str        fp, [sp, #-4]!
  00025664:  add        fp, sp, #0
  00025668:  sub        sp, sp, #0x14
  0002566c:  str        r0, [fp, #-0x10]
  00025670:  ldr        r3, [pc, #0xc8]
  00025674:  add        r3, pc, r3
  00025678:  ldr        r2, [fp, #-0x10]
  0002567c:  cmp        r2, #0
  00025680:  bne        #0x2569c
  00025684:  ldr        r2, [pc, #0xb8]
  00025688:  ldr        r2, [r3, r2]
  0002568c:  str        r2, [fp, #-8]
  00025690:  mov        r2, #0
  00025694:  str        r2, [fp, #-0xc]
  00025698:  b          #0x256b0
  0002569c:  ldr        r2, [pc, #0xa4]
  000256a0:  ldr        r2, [r3, r2]
  000256a4:  str        r2, [fp, #-8]
  000256a8:  mov        r2, #0x30
  000256ac:  str        r2, [fp, #-0xc]
  000256b0:  ldr        r1, [fp, #-8]
  000256b4:  ldrb       r2, [r1, #2]
  000256b8:  bfc        r2, #0, #5
  000256bc:  strb       r2, [r1, #2]
  000256c0:  ldr        r2, [pc, #0x84]
  000256c4:  ldr        r2, [r3, r2]
  000256c8:  ldr        r1, [r2]
  000256cc:  ldr        r2, [fp, #-0xc]
  000256d0:  add        r2, r1, r2
  000256d4:  ldr        r1, [fp, #-8]
  000256d8:  ldr        r1, [r1]
  000256dc:  str        r1, [r2]
  000256e0:  ldr        r1, [fp, #-8]
  000256e4:  ldrb       r2, [r1, #4]
  000256e8:  bfc        r2, #0, #8
  000256ec:  strb       r2, [r1, #4]
  000256f0:  ldr        r1, [fp, #-8]
  000256f4:  ldrb       r2, [r1, #5]
  000256f8:  bfc        r2, #0, #8
  000256fc:  strb       r2, [r1, #5]
  00025700:  ldr        r1, [fp, #-8]
  00025704:  ldrb       r2, [r1, #6]
  00025708:  bfc        r2, #0, #8
  0002570c:  strb       r2, [r1, #6]
  00025710:  ldr        r2, [pc, #0x34]
  00025714:  ldr        r3, [r3, r2]
  00025718:  ldr        r2, [r3]
  0002571c:  ldr        r3, [fp, #-0xc]
  00025720:  add        r3, r2, r3
  00025724:  add        r3, r3, #4
  00025728:  ldr        r2, [fp, #-8]
  0002572c:  ldr        r2, [r2, #4]
  00025730:  str        r2, [r3]
  00025734:  add        sp, fp, #0
  00025738:  ldm        sp!, {fp}
  0002573c:  bx         lr
  00025740:  andeq      r4, r2, r4, asr #24
  00025744:  andeq      r0, r0, r8, lsr r5
  00025748:  strdeq     r0, r1, [r0], -ip
  0002574c:  andeq      r0, r0, r0, ror #9

