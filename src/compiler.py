# Filename: compiler.py
# This file contains the Instruction class for converting every instruction to binary Instruction
# Code. It also contains two global variables for converting operation into OpCode.
# ============================================================
# compiler.py — Member B's Complete File
# ============================================================
# CONNECTIONS THIS FILE DEPENDS ON:
#   bin_convert.py  →  HalfPrecision, Length
#   storage.py      →  memory, register, variable
#   addressing.py   →  NOT imported here; addressing is done
#                       at runtime inside run.py. compiler.py
#                       only produces the binary codes.
#
# CONNECTIONS THAT DEPEND ON THIS FILE:
#   run.py → Program.__init__() calls Instruction.encodeProgram()
#             which fills memory with 32-bit instruction codes.
#             run.py cannot work at all until this file is correct.
# ============================================================


# ────────────────────────────────────────────────────────────
# STEP 1 — IMPORTS + LOOKUP TABLES
# Priority: 🔴 CRITICAL — do this before anything else
# ────────────────────────────────────────────────────────────
#
# WHY: Every method below needs HalfPrecision for binary
# conversions and Length for constants (precision=16,
# instrxn=32, opAddr=7, opMode=4).
# memory and variable are used in encodeProgram().
#
# DO THIS FIRST:

from bin_convert import HalfPrecision, Length
from storage import memory, register, variable

# ── operations ──────────────────────────────────────────────
# Each inner list = one Execute+Write (EW) group.
# Position inside the inner list = Category Code (0,1,2,...).
#
# From the spec's opcode table, grouped by EW bits:
#   EW=11 (Execute=1, Write=1): MOD, ADD, SUB, MUL, DIV
#   EW=10 (Execute=1, Write=0): JEQ, JNE, JLT, JLE, JGT, JGE, JMP
#   EW=01 (Execute=0, Write=1): MOV, CALL, RET, SCAN
#   EW=00 (Execute=0, Write=0): PRNT, EOP/FUNC
#
# WHAT TO WRITE:
# Map every operation name from the spec table to the list below.
# The ORDER within each inner list must match the Category Code
# column in the spec (000=position 0, 001=position 1, etc.).

operations = [
    # EW=00 group  →  operationCodes[0][0] = "00"
    ["PRNT", "EOP", "FUNC"],                        # cat 000, 001, 001

    # EW=01 group  →  operationCodes[0][1] = "01"
    ["MOV", "CALL", "RET", "SCAN"],                 # cat 000, 001, 010, 011

    # EW=10 group  →  operationCodes[0][2] = "10"
    ["JEQ", "JNE", "JLT", "JLE", "JGT", "JGE", "JMP"],  # cat 000–110

    # EW=11 group  →  operationCodes[0][3] = "11"
    ["MOD", "ADD", "SUB", "MUL", "DIV"],            # cat 000–100
]

# ── operationCodes ───────────────────────────────────────────
# [0] = EW bits for each group index (index matches operations list above)
# [1] = category code strings by position within a group

operationCodes = [
    ["00", "01", "10", "11"],                           # EW bits per group
    ["000", "001", "010", "011", "100", "101", "110"],  # category codes
]

# ── SELF-CHECK ───────────────────────────────────────────────
# Manually verify ADD before moving on:
#   ADD is in operations[3] at position 1
#   operationCodes[0][3] = "11"   → Execute=1, Write=1  ✓
#   operationCodes[1][1] = "001"  → Category 001        ✓
#   Final OpCode = "11" + "001" = "11001"               ✓ matches spec
# ────────────────────────────────────────────────────────────


class Instruction:

    # ──────────────────────────────────────────────────────────
    # STEP 2 — decodeMSG(msg)
    # Priority: 🟡 LOW — only needed if your group does SCAN/PRNT
    # ──────────────────────────────────────────────────────────
    #
    # WHY: SCAN/PRNT use a message operand like "M:Hello-World".
    # The encoded message uses - for space, _ for tab, -_ for
    # newline, the word "minus" for a literal dash, and the word
    # "under" for a literal underscore.
    #
    # CRITICAL ORDER: replace "-_" BEFORE replacing "-", or the
    # dash in "-_" gets swapped to space first and you never
    # catch the pair.
    #
    # WHAT TO WRITE:

    @staticmethod
    def decodeMSG(msg):
        msg = msg.replace("-_", "\n")   # MUST be first
        msg = msg.replace("-", " ")
        msg = msg.replace("_", "\t")
        msg = msg.replace("minus", "-")
        msg = msg.replace("under", "_")
        return msg

    # ── SELF-CHECK ─────────────────────────────────────────────
    # decodeMSG("Hello-World") → "Hello World"
    # decodeMSG("line1-_line2") → "line1\nline2"
    # decodeMSG("minus_sign") → "-\tsign"   (minus→-, then _→tab)
    # ──────────────────────────────────────────────────────────


    # ──────────────────────────────────────────────────────────
    # STEP 3 — encodeOp(operand)
    # Priority: 🔴 CRITICAL — hardest method, build branch by branch
    # ──────────────────────────────────────────────────────────
    #
    # WHAT IT RETURNS:
    #   • Immediate operand → 16-bit HP binary string (full precision)
    #   • All other operands → 10-bit string: [4-bit mode][6-bit addr]
    #     Always call .zfill(10) at the end of every non-immediate branch.
    #
    # FROM bin_convert.py you'll use:
    #   HalfPrecision.hpdec2bin(number) → 16-bit binary string
    #   Length.addZeros(value, strlen)  → pads binary to strlen digits
    #   Length.precision = 16           → for detecting immediate return
    #
    # FROM storage.py you'll use:
    #   variable.load(name) → returns the numeric address of a named
    #                          variable/register (e.g. variable.load('R1') → 1)
    #
    # MODE CODES (from spec section IV.3 / IV.6):
    #   "0000" = Register
    #   "0001" = Register Indirect
    #   "0010" = Direct (memory)
    #   "0011" = Indirect (memory)
    #   "0100" = Indexed (register/memory displacement)
    #   "0101" = Indexed (integer displacement)
    #   "0110" = Auto-Increment
    #   "0111" = Auto-Decrement
    #
    # ADDRESS PORTION (6 bits):
    #   For register/memory names: variable.load(name) gives the address.
    #   For integer displacements: the leftmost bit of the 7-bit Op1Addr
    #     is the sign bit (0=positive, 1=negative); the remaining 6 bits
    #     are the magnitude. So a 7-bit field = [sign][6-bit magnitude].
    #
    # BUILD ONE BRANCH AT A TIME — test each before writing the next.
    #
    # WHAT TO WRITE:

    @staticmethod
    def encodeOp(operand):

        # ── BRANCH 1: Immediate (operand is a plain number) ────
        # 🔴 CRITICAL — build and test this first
        #
        # How to detect: try casting to float. If it works, it's a number.
        # Return the full 16-bit HP binary — NOT 10 bits. This is the
        # special case; the caller (encode) handles it differently.

        try:
            val = float(operand)
            return HalfPrecision.hpdec2bin(val)   # returns 16-bit string
        except (ValueError, TypeError):
            pass

        # ── BRANCH 2: Message operand (optional, for SCAN/PRNT) ─
        # 🟡 LOW priority

        if 'M:' in operand:
            msg_text = operand.replace('M:', '')
            decoded = Instruction.decodeMSG(msg_text)
            idx = variable.data['MI']
            variable.data['MSG'][idx] = decoded
            variable.data['MI'] += 1
            return '0' * 10   # placeholder 10-bit code

        # ── BRANCH 3: Operand HAS parentheses ──────────────────
        # 🔴 CRITICAL

        if '(' in operand and ')' in operand:
            inner = operand.replace('(', '').replace(')', '')

            # Sub-branch 3a: Indexed / Based / Relative (X, Y, Z prefix)
            # 🔴 CRITICAL
            #
            # X → Indexed, Y → Based, Z → Relative
            # After stripping the prefix letter, what remains is either:
            #   • A plain integer (positive or negative) → integer displacement
            #   • A register name (contains R, PC, or ACC) → register disp
            #   • Anything else → memory displacement
            #
            # Mode codes for Indexed:
            #   register/memory displacement → "0100"
            #   integer displacement         → "0101"
            #
            # For Based (Y) and Relative (Z) the mode codes are the same
            # pattern but the rb bit in encode() distinguishes them at the
            # instruction level. encodeOp() itself just returns the same
            # 4-bit mode code as indexed.
            #
            # Address field construction:
            #   Integer: [sign_bit (1 bit)][magnitude (6 bits)] = 7 bits total
            #     → but Op1Addr is 7 bits wide (opAddr=7), leftmost is sign
            #     → sign_bit: '0' if positive, '1' if negative
            #     → magnitude: Length.addZeros(abs(int(disp)), 6)
            #   Register/Memory: variable.load(name) → Length.addZeros(addr, 6)
            #     → prepend '0' as the displacement-type flag bit → 7 bits

            if inner[0] in ('X', 'Y', 'Z'):
                prefix = inner[0]
                remaining = inner[1:]

                try:
                    # Integer displacement
                    disp_int = int(remaining)
                    sign_bit = '1' if disp_int < 0 else '0'
                    mag = Length.addZeros(abs(disp_int), 6)
                    mode = '0101'                       # indexed, integer disp
                    addr_field = sign_bit + mag         # 7 bits
                    return (mode + addr_field).zfill(10)

                except ValueError:
                    # Register or memory displacement
                    addr = int(variable.load(remaining))
                    addr_bits = Length.addZeros(addr, 6)
                    mode = '0100'                       # indexed, reg/mem disp
                    # Displacement type flag: 0 = from register, 1 = from memory
                    # Registers contain 'R', 'PC', 'ACC', 'XR', 'BR', 'CR', etc.
                    is_reg = any(r in remaining for r in ('R', 'PC', 'ACC', 'XR', 'BR', 'IR', 'CR', 'JR'))
                    type_bit = '0' if is_reg else '1'
                    addr_field = type_bit + addr_bits   # 7 bits
                    return (mode + addr_field).zfill(10)

            # Sub-branch 3b: Auto-Increment  (e.g. "R1+")
            # 🟠 HIGH priority
            if '+' in inner:
                reg_name = inner.replace('+', '')
                mode = '0110'
                addr = int(variable.load(reg_name))
                return (mode + Length.addZeros(addr, 6)).zfill(10)

            # Sub-branch 3c: Auto-Decrement  (e.g. "R1-")
            # 🟠 HIGH priority
            if '-' in inner:
                reg_name = inner.replace('-', '')
                mode = '0111'
                addr = int(variable.load(reg_name))
                return (mode + Length.addZeros(addr, 6)).zfill(10)

            # Sub-branch 3d: Register Indirect  (e.g. "(R1)", "(PC)")
            # 🔴 CRITICAL
            if any(r in inner for r in ('R', 'PC', 'ACC')):
                mode = '0001'
                addr = int(variable.load(inner))
                return (mode + Length.addZeros(addr, 6)).zfill(10)

            # Sub-branch 3e: Indirect (memory)  (e.g. "(A)")
            # 🔴 CRITICAL
            mode = '0011'
            addr = int(variable.load(inner))
            return (mode + Length.addZeros(addr, 6)).zfill(10)

        # ── BRANCH 4: No parentheses, not a number ─────────────
        # 🔴 CRITICAL

        # Register mode: name contains R, PC, or ACC
        if any(r in operand for r in ('R', 'PC', 'ACC')):
            mode = '0000'
        else:
            # Direct (memory variable like A, B, XR, BR, etc.)
            mode = '0010'

        addr = int(variable.load(operand))
        return (mode + Length.addZeros(addr, 6)).zfill(10)

    # ── SELF-CHECK ─────────────────────────────────────────────
    # After writing encodeOp, test these in a scratch file:
    #
    #   encodeOp("5.0")   → 16-char binary (HP of 5.0)
    #   encodeOp("R1")    → "0000" + addZeros(1, 6) = "0000000001"
    #   encodeOp("(R1)")  → "0001" + addZeros(1, 6) = "0001000001"
    #   encodeOp("(R1+)") → "0110" + addZeros(1, 6) = "0110000001"
    #   encodeOp("A")     → "0010" + addZeros(1, 6) = "0010000001"
    #   encodeOp("(A)")   → "0011" + addZeros(1, 6) = "0011000001"
    # ──────────────────────────────────────────────────────────


    # ──────────────────────────────────────────────────────────
    # STEP 4 — encode(inst)
    # Priority: 🔴 CRITICAL — depends entirely on encodeOp being correct
    # ──────────────────────────────────────────────────────────
    #
    # INSTRUCTION CODE FORMAT (32 bits total):
    #
    #  Bit:  0    1    2  3  4    5    6  7  8    9..15   16   17 18 19   20..26   27..31
    #        [  Execute ] [  Write ] [ Category ]  [ib]  [Op1Mode] [Op1Addr] [rb] [Op2Mode] [Op2Addr] [Extra]
    #
    # Simplified layout the spec uses:
    #   bits 0–1  = EW (Execute, Write) bits
    #   bits 2–4  = Category Code
    #   bit  5    = ib (Immediate Bit): 1 if Op2 is immediate
    #   bits 6–8  = Op1 Mode (3 bits)
    #   bits 9–15 = Op1 Addr (7 bits)
    #   bit  16   = rb (Relative Bit): 1 if Op2 is relative/based
    #   bits 17–19 = Op2 Mode (3 bits)
    #   bits 20–26 = Op2 Addr (7 bits)
    #   bits 27–31 = Extra bits (used by immediate for Op2's HP value tail)
    #
    # ALIASED OPERATIONS that must be transformed BEFORE looking up OpCode:
    #
    #   CB   → ADD 'BR', <block_name>
    #          (Op1 becomes 'BR', Op2 stays as the block label)
    #   CF   → ADD 'BR', <function_block_name>
    #          (same as CB but for F1–F4)
    #   CMP  → SUB 'JR', <operand>
    #          (Op1 becomes 'JR', computes difference stored in JR)
    #   JEQ/JNE/JLT/JLE/JGT/JGE/JMP
    #        → Keep the J-operation name, Op1 is the block/function name
    #   ADDPC → MOV <Op1>, <Z + Op2>
    #           (rewrite Op2 with 'Z' prefix to trigger relative mode)
    #   CALL  → TWO instructions:
    #             1) MOV PC CR   (save PC into CR)
    #             2) MOV <F_block> PC  (jump to function)
    #   RET   → TWO instructions:
    #             1) MOV CR PC   (restore PC from CR)
    #             2) MOV <operand> ACC  (store return value)
    #   FUNC  → All-zero 32-bit string immediately (marks function boundary)
    #
    # WHAT TO WRITE:

    @staticmethod
    def encode(inst):

        parts = inst.split()
        op = parts[0]
        op1 = parts[1] if len(parts) > 1 else None
        op2 = parts[2] if len(parts) > 2 else None

        # ── Sub-step 4a: Handle FUNC immediately ───────────────
        # 🔴 CRITICAL — must be first check
        if op == 'FUNC':
            return '0' * Length.instrxn   # 32 zeros

        # ── Sub-step 4a: Transform aliased operations ──────────
        # 🔴 CRITICAL
        #
        # CALL and RET expand to two instructions. We return a LIST of two
        # 32-bit strings when this happens. encodeProgram() must handle lists.

        if op == 'CB' or op == 'CF':
            op2 = op1       # original block name becomes Op2
            op1 = 'BR'      # Op1 is always BR
            op = 'ADD'

        elif op == 'CMP':
            op2 = op1       # what was Op1 becomes Op2
            op1 = 'JR'
            op = 'SUB'

        elif op == 'ADDPC':
            # Op2 gets a Z prefix to trigger relative mode encoding
            op2 = 'Z' + op2
            op = 'MOV'

        elif op == 'CALL':
            # Expand into two separate MOV instructions
            inst1 = Instruction.encode('MOV PC CR')
            inst2 = Instruction.encode(f'MOV {op1} PC')
            return [inst1, inst2]

        elif op == 'RET':
            # Expand into two separate MOV instructions
            inst1 = Instruction.encode('MOV CR PC')
            inst2 = Instruction.encode(f'MOV {op1} ACC')
            return [inst1, inst2]

        # ── Sub-step 4b: Look up OpCode (5 bits) ───────────────
        # 🔴 CRITICAL
        #
        # Find op in the operations list. The outer list index gives the
        # EW group; the inner list position gives the Category Code index.
        #
        # WHAT TO WRITE:

        opcode = None
        for group_idx, group in enumerate(operations):
            if op in group:
                cat_idx = group.index(op)
                ew_bits = operationCodes[0][group_idx]
                cat_bits = operationCodes[1][cat_idx]
                opcode = ew_bits + cat_bits   # 5 bits total
                break

        if opcode is None:
            raise ValueError(f"Unknown operation: {op}")

        # ── Sub-step 4c: Determine ib (Immediate Bit) ──────────
        # 🟠 HIGH priority
        #
        # ib = '1' if Op2 is an immediate value (a number).
        # You can tell because encodeOp() returns a 16-bit string for
        # immediates, vs a 10-bit string for everything else.
        #
        # ib = '0' by default.

        ib = '0'
        rb = '0'
        encoded_op1 = ''
        encoded_op2_mode = ''
        encoded_op2_addr = ''
        extra_bits = '00000'   # bits 27–31

        # Encode Op1 (always present after transformation)
        raw_op1_code = Instruction.encodeOp(op1)
        # Op1 is never immediate, so raw_op1_code is always 10 bits.
        # Layout: raw_op1_code = [4-bit mode][6-bit addr]
        # But in the instruction: bits 6–8 = Op1Mode (3 bits), bits 9–15 = Op1Addr (7 bits)
        # encodeOp returns 4 mode bits + 6 addr bits = 10 bits total.
        # The instruction format uses 3 mode bits + 7 addr bits = 10 bits.
        # The top mode bit from the spec is folded into the addr field (displacement type).
        # So: mode = raw_op1_code[0:3], addr = raw_op1_code[3:10] — wait, that's 3+7=10. ✓
        op1_mode = raw_op1_code[0:3]    # bits 6–8: 3-bit mode code
        op1_addr = raw_op1_code[3:10]   # bits 9–15: 7-bit address (includes disp flag)

        # Encode Op2 (if present)
        if op2 is not None:
            raw_op2_code = Instruction.encodeOp(op2)

            if len(raw_op2_code) == Length.precision:
                # Immediate: ib = 1, extra bits hold last 5 bits of HP binary
                ib = '1'
                extra_bits = raw_op2_code[11:]  # last 5 bits of 16-bit HP
                encoded_op2_mode = '000'
                encoded_op2_addr = '0000000'
            else:
                # Non-immediate: check for relative/based (Z or Y prefix in original op2)
                if op2 and op2[0] in ('Z', 'Y'):
                    rb = '1'
                op2_mode = raw_op2_code[0:3]
                op2_addr = raw_op2_code[3:10]
                encoded_op2_mode = op2_mode
                encoded_op2_addr = op2_addr
        else:
            # No Op2: fill zeros
            encoded_op2_mode = '000'
            encoded_op2_addr = '0000000'

        # ── Sub-step 4d: Concatenate into 32 bits ──────────────
        # 🔴 CRITICAL
        #
        # Layout:
        #   opcode(5) + ib(1) + op1_mode(3) + op1_addr(7) +
        #   rb(1) + op2_mode(3) + op2_addr(7) + extra(5)
        #   = 5+1+3+7+1+3+7+5 = 32 ✓

        instruction_code = (
            opcode +            # bits 0–4  (5 bits)
            ib +                # bit  5    (1 bit)
            op1_mode +          # bits 6–8  (3 bits)
            op1_addr +          # bits 9–15 (7 bits)
            rb +                # bit  16   (1 bit)
            encoded_op2_mode +  # bits 17–19 (3 bits)
            encoded_op2_addr +  # bits 20–26 (7 bits)
            extra_bits          # bits 27–31 (5 bits)
        )

        return instruction_code.zfill(Length.instrxn)

    # ── SELF-CHECK ─────────────────────────────────────────────
    # After writing encode(), test these in a scratch file:
    #
    #   encode("ADD R1 R2")
    #     → opcode = "11001"
    #     → ib = '0', rb = '0'
    #     → op1: R1 → mode "000", addr = addZeros(1,7) = "0000001"
    #     → op2: R2 → mode "000", addr = addZeros(2,7) = "0000010"
    #     → result = "11001" + "0" + "000" + "0000001" + "0" + "000" + "0000010" + "00000"
    #     → Verify it is exactly 32 characters long.
    #
    #   encode("MOV R1 5.0")
    #     → ib = '1'  (Op2 is immediate)
    #     → extra_bits = last 5 bits of hpdec2bin(5.0)
    #     → encoded_op2_mode and addr become all zeros
    #
    #   encode("FUNC")
    #     → "00000000000000000000000000000000" (32 zeros)
    # ──────────────────────────────────────────────────────────


    # ──────────────────────────────────────────────────────────
    # STEP 5 — encodeProgram(program)
    # Priority: 🔴 CRITICAL — final step, writes instructions into memory
    # ──────────────────────────────────────────────────────────
    #
    # WHAT THIS METHOD DOES:
    #   • Reads every raw instruction string from `program` (list of lines)
    #   • Skips comments (x = single line, z...z = multiline block)
    #   • Encodes each instruction using encode()
    #   • CB/CF instructions get inserted at the FRONT of the list
    #     (because they define block addresses; run.py needs them first)
    #   • All other instructions are appended in order
    #   • After processing, stores block count into BR's register slot
    #   • Writes every encoded instruction into memory starting at BR's address
    #
    # CONNECTIONS:
    #   variable.load('BR') → starting memory address (= 9 from storage.py)
    #   memory.store(addr, code) → stores the 32-bit string at that address
    #   register.store(variable.load('BR'), count) → saves block count
    #
    # WHAT TO WRITE:

    @staticmethod
    def encodeProgram(program):

        # ── α: Initialize ──────────────────────────────────────
        # 🔴 CRITICAL — set these up before the loop
        #
        # addr: the memory address where the first instruction goes.
        #       Get it from variable.load('BR') which returns 9.
        # instructions: the ordered list we'll build up. CB/CF go at front.
        # block_counter: tracks the insertion point for CB/CF instructions.
        #                Each CB/CF inserted pushes this counter up by 1.
        # multiline_comment: flag — True when we're inside a z...z block.

        addr = int(variable.load('BR'))         # starts at 9
        instructions = []
        block_counter = 0
        multiline_comment = False

        # ── β: Loop through every line ─────────────────────────
        # 🔴 CRITICAL

        for line in program:

            # Skip empty lines
            line = line.strip()
            if not line:
                continue

            # Toggle multiline comment on/off when line starts with 'z'
            if line[0] == 'z':
                multiline_comment = not multiline_comment
                continue

            # Skip lines inside a multiline comment block
            if multiline_comment:
                continue

            # Skip single-line comments
            if line[0] == 'x':
                continue

            # ── γ: CB / CF — insert at front ───────────────────
            # 🔴 CRITICAL
            #
            # CB and CF define block entry points. The block's address
            # must be stored into the block's register BEFORE encoding,
            # because encodeOp() for the block operand will call
            # variable.load() to get that address.
            #
            # Steps:
            #   1. Get the current addr value.
            #   2. Convert it to HP binary: HalfPrecision.hpdec2bin(addr)
            #   3. Store it into the block's register slot:
            #      register.store(variable.load(block_name), hp_addr)
            #   4. Encode the instruction (now variable.load(block_name) has addr).
            #   5. Insert encoded instruction at position block_counter in the list.
            #   6. Increment block_counter.
            #   7. Increment addr by 1.

            parts = line.split()
            op = parts[0]

            if op in ('CB', 'CF'):
                block_name = parts[1]
                hp_addr = HalfPrecision.hpdec2bin(addr)
                register.store(int(variable.load(block_name)), hp_addr)
                encoded = Instruction.encode(line)
                # encode() won't expand CB/CF into a list, it returns a string.
                # (CB/CF go through the CB branch in encode which rewrites to ADD.)
                if isinstance(encoded, list):
                    for e in encoded:
                        instructions.insert(block_counter, e)
                        block_counter += 1
                        addr += 1
                else:
                    instructions.insert(block_counter, encoded)
                    block_counter += 1
                    addr += 1

            else:
                # ── δ: All other instructions — append to end ───
                # 🟠 HIGH priority
                #
                # encode() may return a list (CALL, RET expand to two instructions).
                # Handle both a single string and a list of strings.

                encoded = Instruction.encode(line)
                if isinstance(encoded, list):
                    for e in encoded:
                        instructions.append(e)
                        addr += 1
                else:
                    instructions.append(encoded)
                    addr += 1

        # ── ε: Store block count into BR ───────────────────────
        # 🔴 CRITICAL
        #
        # run.py uses the value stored at register[BR] to know how many
        # block definition instructions sit at the front of memory before
        # the actual program instructions begin.
        #
        # register address of BR = variable.load('BR') = 9
        # The value to store = block_counter (number of CB/CF instructions)

        br_reg_addr = int(variable.load('BR'))
        register.store(br_reg_addr, block_counter)

        # ── ζ: Write instructions into memory ──────────────────
        # 🔴 CRITICAL
        #
        # Start writing from the BR address (9).
        # Each instruction occupies one memory slot.
        # memory.store(address, instruction_string) handles the rest.

        start_addr = int(variable.load('BR'))   # = 9
        for i, code in enumerate(instructions):
            memory.store(start_addr + i, code)

    # ── SELF-CHECK ─────────────────────────────────────────────
    # After writing encodeProgram(), test with a minimal program:
    #
    #   from storage import memory, register, variable
    #   from compiler import Instruction
    #
    #   program = [
    #       "x this is a comment",
    #       "MOV R1 R2",
    #       "ADD R1 R2",
    #   ]
    #   Instruction.encodeProgram(program)
    #
    #   # Inspect raw memory contents:
    #   print(memory.data[9])   # first instruction binary string
    #   print(memory.data[10])  # second instruction binary string
    #
    #   # Each should be a 32-character binary string.
    #   # memory.load(9) will return the HP decimal, not the raw binary,
    #   # so always use memory.data[addr] to inspect the raw instruction code.
    # ──────────────────────────────────────────────────────────


# ============================================================
# FINAL EXPECTED STRUCTURE OF compiler.py
# ============================================================
#
# compiler.py
# │
# ├── from bin_convert import HalfPrecision, Length
# ├── from storage import memory, register, variable
# │
# ├── operations = [ [...], [...], [...], [...] ]
# │     └── 4 groups, each group ordered by Category Code
# │
# ├── operationCodes = [ [EW bits...], [Cat codes...] ]
# │
# └── class Instruction:
#       ├── decodeMSG(msg)       🟡 LOW   — string replacements only
#       ├── encodeOp(operand)    🔴 CRIT  — returns 10-bit or 16-bit code
#       ├── encode(inst)         🔴 CRIT  — returns 32-bit instruction string
#       └── encodeProgram(prog)  🔴 CRIT  — fills memory, called by run.py
#
# ── HOW run.py CALLS THIS FILE ────────────────────────────
#
# run.py:
#   from compiler import Instruction
#
#   class Program:
#       def __init__(self, program):
#           Instruction.encodeProgram(program)  ← this is the only call
#
#   # After this, memory.data[9], memory.data[10], ... hold
#   # the 32-bit instruction strings that Program.run() will fetch.
#
# ── CODING ORDER (safest path) ────────────────────────────
#
#   1. Imports + operations + operationCodes  (get lookup tables right)
#   2. encodeOp() Branch 1 (immediate only)   → test
#   3. encodeOp() Branch 4 (register + direct) → test
#   4. encodeOp() Branch 3 (parentheses, one sub-branch at a time) → test each
#   5. encode() simple case: ADD R1 R2        → test
#   6. encode() aliased ops: CB, CF, CMP, CALL, RET, ADDPC
#   7. encodeProgram() — only after encode() is verified
#
# ── WHAT BREAKS IF SOMETHING IS WRONG ────────────────────
#
#   If encodeOp() returns wrong mode code → wrong addressing at runtime
#   If encode() wrong bit layout → run.py reads garbage opcodes
#   If encodeProgram() wrong addr sequence → instructions in wrong slots
#   All three failures are silent until run.py crashes or produces
#   wrong output — so test each method independently first.
# ============================================================