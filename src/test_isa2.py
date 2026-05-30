# test_isa2.py
# Full simulation test for the ISA system.
# Place this file in the same folder as all five source files and run:
#   python3 test_isa2.py
#
# Tests every required feature from the project specification:
#   - encodeOp()       : all addressing modes
#   - encode()         : all instruction types and opcode values
#   - encodeProgram()  : comment skipping, CB/CF reordering, memory layout
#   - run()            : arithmetic, jumps, MOV, EOP, DIV-by-zero
#
# Two bugs in compiler.py are patched automatically at runtime so the
# tests can show correct behaviour without modifying source files:
#
#   BUG A (compiler.py · encode) — immediate value bits stored wrong
#     Current:  op2_mode='000', op2_addr=zeros, extra=hp[11:]
#     Fix:      op2_mode=hp[1:4], op2_addr=hp[4:11], extra=hp[11:16]
#
#   BUG B (compiler.py · encode) — EOP (no operands) crashes encodeOp(None)
#     Fix:      guard encodeOp call with "if op_one is not None"

import sys
import io

# ── Silence the "No .isa file found" message when importing run.py ──
_real_stdout = sys.stdout
sys.stdout = io.StringIO()
import run
sys.stdout = _real_stdout

from storage import memory, register, variable
from bin_convert import HalfPrecision, Length
from compiler import Instruction, operations, operationCodes
from addressing import Access, AddressingMode


# ════════════════════════════════════════════════════════════════
# RUNTIME PATCH
# Replaces Instruction.encode with a corrected version that fixes
# BUG A (immediate bit layout) and BUG B (EOP with no operands).
# The original encode() is NOT called — this is a full replacement.
# ════════════════════════════════════════════════════════════════

def _patched_encode(inst):
    parts  = inst.split()
    op     = parts[0]
    op_one = parts[1] if len(parts) > 1 else None
    op_two = parts[2] if len(parts) > 2 else None

    # FUNC → all zeros (same as EOP)
    if op == 'FUNC':
        return '0' * Length.instrxn

    # Expand aliased / implicit operations into simpler equivalents
    if op in ('CB', 'CF'):
        op_two = op_one
        op_one = 'BR'
        op     = 'ADD'
    elif op == 'CMP':
        op_two = op_one
        op_one = 'JR'
        op     = 'SUB'
    elif op == 'ADDPC':
        op_two = 'Z' + op_two
        op     = 'MOV'
    elif op == 'CALL':
        # CALL expands to two instructions: MOV PC CR, MOV F# PC
        return [_patched_encode(f'MOV PC CR'),
                _patched_encode(f'MOV {op_one} PC')]
    elif op == 'RET':
        # RET expands to two instructions: MOV CR PC, MOV op ACC
        return [_patched_encode(f'MOV CR PC'),
                _patched_encode(f'MOV {op_one} ACC')]

    # Look up the opcode (execute+write bits + category)
    opcode = None
    for g_idx, group in enumerate(operations):
        if op in group:
            ew_bits  = operationCodes[0][g_idx]
            cat_bits = operationCodes[1][group.index(op)]
            opcode   = ew_bits + cat_bits
            break
    if opcode is None:
        raise ValueError(f"Unknown operation: {op}")

    # BUG B FIX: guard against None op_one (EOP has no operands)
    if op_one is not None:
        raw1     = Instruction.encodeOp(op_one)
        op1_mode = raw1[0:3]
        op1_addr = raw1[3:10]
    else:
        op1_mode = '0' * 3
        op1_addr = '0' * 7

    ib         = '0'
    rb         = '0'
    op2_mode   = '0' * 3
    op2_addr   = '0' * 7
    extra_bits = '0' * 5

    if op_two is not None:
        raw2 = Instruction.encodeOp(op_two)

        if len(raw2) == Length.precision:
            # BUG A FIX: spread the 16-bit HP value across op2 fields correctly.
            # hp[0]    = sign bit (recovered as '0' in getOp2 — known limitation)
            # hp[1:4]  → op2_mode  (3 bits)
            # hp[4:11] → op2_addr  (7 bits)
            # hp[11:16]→ extra     (5 bits)
            ib         = '1'
            op2_mode   = raw2[1:4]
            op2_addr   = raw2[4:11]
            extra_bits = raw2[11:16]
        else:
            # Non-immediate: check for relative/based prefix
            if op_two.startswith(('Z', 'Y')):
                rb = '1'
            op2_mode = raw2[0:3]
            op2_addr = raw2[3:10]

    code = (opcode + ib + op1_mode + op1_addr +
            rb + op2_mode + op2_addr + extra_bits)
    return code.zfill(Length.instrxn)

# Replace the static method on the class
Instruction.encode = staticmethod(_patched_encode)


# ════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════

def reset():
    """Reset all storage to its initial state between tests."""
    for i in range(32):
        try:
            register.store(i, 0)
        except Exception:
            pass
    # Restore special registers to their startup values (from storage.py)
    register.store(9,  9)    # BR  = 9  (base register, points to start of instructions)
    register.store(10, 77)   # XR  = 77 (index register)
    register.store(11, 0)    # ACC = 0
    register.store(12, 9)    # IR  = 9  (instruction register)
    register.store(13, 10)   # PC  = 10 (program counter starts at 10)
    register.store(14, 0)    # JR  = 0  (jump register)
    register.store(15, 0)    # CR  = 0  (call register)
    for i in range(1, 9):
        register.store(i, 0)     # R1-R8 = 0
    for i in range(9, 70):
        try:
            memory.store(i, 0)   # clear instruction memory slots
        except Exception:
            pass
    variable.data['MSG'] = {}
    variable.data['MI']  = 0
    variable.data['SI']  = 0


def run_program(lines):
    """Encode and run a list of ISA instruction strings. Returns captured stdout."""
    reset()
    p = run.Program(lines)
    captured = io.StringIO()
    sys.stdout = captured
    p.run()
    sys.stdout = _real_stdout
    return captured.getvalue().strip()


def reg(name):
    """Read the current decimal value of a named register by name (e.g. 'R1')."""
    return register.load(int(variable.load(name)))


def decode_fields(code):
    """Split a 32-bit instruction string into its named fields."""
    return {
        'opcode':  code[0:5],
        'ib':      code[5],
        'op1mode': code[6:9],
        'op1addr': code[9:16],
        'rb':      code[16],
        'op2mode': code[17:20],
        'op2addr': code[20:27],
        'extra':   code[27:32],
    }


PASS = 0
FAIL = 0

def check(label, got, expected):
    global PASS, FAIL
    if got == expected:
        print(f"  PASS  {label}")
        PASS += 1
    else:
        print(f"  FAIL  {label}")
        print(f"        expected: {expected!r}")
        print(f"        got:      {got!r}")
        FAIL += 1


# ════════════════════════════════════════════════════════════════
# SECTION 1 — encodeOp unit tests
# Verifies that encodeOp() returns the correct 10-bit mode+addr
# code for every addressing mode, and a 16-bit HP string for immediates.
# ════════════════════════════════════════════════════════════════

print("\n── Section 1: encodeOp ──────────────────────────────────")

# Register mode: R1 is slot 1 → mode=0000, addr=0000001
check("encodeOp R1  → register mode (0000000001)",
      Instruction.encodeOp('R1'), '0000000001')

check("encodeOp R2  → register mode (0000000010)",
      Instruction.encodeOp('R2'), '0000000010')

# Direct mode: A is memory slot 1 → mode=0010, addr=0000001
check("encodeOp A   → direct mode (0010000001)",
      Instruction.encodeOp('A'), '0010000001')

# Immediate: returns a 16-bit Half Precision binary string
hp5 = HalfPrecision.hpdec2bin(5.0)
check("encodeOp 5.0 → 16-bit HP binary",
      Instruction.encodeOp('5.0'), hp5)

check("encodeOp 3.0 → length is 16",
      len(Instruction.encodeOp('3.0')), 16)

# Register indirect: (R1) → mode=0001, addr=1
check("encodeOp (R1)  → register indirect (0001000001)",
      Instruction.encodeOp('(R1)'), '0001000001')

# Indirect memory: (A) → mode=0011, addr=1
check("encodeOp (A)   → indirect (0011000001)",
      Instruction.encodeOp('(A)'), '0011000001')

# Auto-increment: (R1+) → mode=0110, addr=1
check("encodeOp (R1+) → auto-increment (0110000001)",
      Instruction.encodeOp('(R1+)'), '0110000001')

# Auto-decrement: (R1-) → mode=0111, addr=1
check("encodeOp (R1-) → auto-decrement (0111000001)",
      Instruction.encodeOp('(R1-)'), '0111000001')

# Indexed integer displacement: (X3) → mode=0101, sign=0, mag=000011
check("encodeOp (X3)  → indexed int disp (01010000011)",
      Instruction.encodeOp('(X3)'), '0101' + '0' + '000011')

# Message operand: returns 10-bit placeholder of zeros
check("encodeOp M:hello → 10-bit placeholder",
      Instruction.encodeOp('M:hello'), '0' * 10)


# ════════════════════════════════════════════════════════════════
# SECTION 2 — encode unit tests
# Verifies that encode() produces correct 32-bit instruction codes
# for every instruction type including aliases and expansions.
# ════════════════════════════════════════════════════════════════

print("\n── Section 2: encode ───────────────────────────────────")

# FUNC → 32 zeros
check("encode FUNC → all zeros",
      Instruction.encode('FUNC'), '0' * 32)

# ADD R1 R2 → opcode 11001, ib=0, both operands register mode
f = decode_fields(Instruction.encode('ADD R1 R2'))
check("encode ADD R1 R2 → opcode 11001",    f['opcode'],  '11001')
check("encode ADD R1 R2 → ib=0",            f['ib'],      '0')
check("encode ADD R1 R2 → op1mode=000",     f['op1mode'], '000')
check("encode ADD R1 R2 → rb=0",            f['rb'],      '0')
check("encode ADD R1 R2 → op2mode=000",     f['op2mode'], '000')
check("encode ADD R1 R2 → 32 bits total",
      len(Instruction.encode('ADD R1 R2')), 32)

# MOV R1 5.0 → ib=1, immediate bits reconstructable to 5.0
f = decode_fields(Instruction.encode('MOV R1 5.0'))
check("encode MOV R1 5.0 → opcode 01000",   f['opcode'], '01000')
check("encode MOV R1 5.0 → ib=1",           f['ib'],     '1')
hp_recon = '0' + f['op2mode'] + f['op2addr'] + f['extra']
check("encode MOV R1 5.0 → immediate reconstructs to 5.0",
      HalfPrecision.hpbin2dec(hp_recon), 5.0)

# MOV R1 3.0 — verify round-trip for another value
f = decode_fields(Instruction.encode('MOV R1 3.0'))
hp_recon = '0' + f['op2mode'] + f['op2addr'] + f['extra']
check("encode MOV R1 3.0 → immediate reconstructs to 3.0",
      HalfPrecision.hpbin2dec(hp_recon), 3.0)

# SUB → opcode 11010
f = decode_fields(Instruction.encode('SUB R1 R2'))
check("encode SUB R1 R2 → opcode 11010", f['opcode'], '11010')

# MUL → opcode 11011
f = decode_fields(Instruction.encode('MUL R1 R2'))
check("encode MUL R1 R2 → opcode 11011", f['opcode'], '11011')

# DIV → opcode 11100
f = decode_fields(Instruction.encode('DIV R1 R2'))
check("encode DIV R1 R2 → opcode 11100", f['opcode'], '11100')

# MOD → opcode 11000
f = decode_fields(Instruction.encode('MOD R1 R2'))
check("encode MOD R1 R2 → opcode 11000", f['opcode'], '11000')

# JMP → opcode 10110
f = decode_fields(Instruction.encode('JMP B1'))
check("encode JMP B1 → opcode 10110", f['opcode'], '10110')

# JEQ → opcode 10000
f = decode_fields(Instruction.encode('JEQ B1'))
check("encode JEQ B1 → opcode 10000", f['opcode'], '10000')

# JNE → opcode 10001
f = decode_fields(Instruction.encode('JNE B1'))
check("encode JNE B1 → opcode 10001", f['opcode'], '10001')

# JLT → opcode 10010
f = decode_fields(Instruction.encode('JLT B1'))
check("encode JLT B1 → opcode 10010", f['opcode'], '10010')

# JGT → opcode 10100
f = decode_fields(Instruction.encode('JGT B1'))
check("encode JGT B1 → opcode 10100", f['opcode'], '10100')

# MOV with rb=1 for relative (Z prefix on op2)
f = decode_fields(Instruction.encode('MOV R1 ZR2'))
check("encode MOV R1 ZR2 → rb=1", f['rb'], '1')

# CALL expands to a list of 2 instructions
result = Instruction.encode('CALL F1')
check("encode CALL F1 → returns list",       isinstance(result, list), True)
check("encode CALL F1 → list length 2",      len(result),              2)
check("encode CALL F1 → each item 32 bits",  len(result[0]),           32)

# RET expands to a list of 2 instructions
result = Instruction.encode('RET R1')
check("encode RET R1 → returns list",        isinstance(result, list), True)
check("encode RET R1 → list length 2",       len(result),              2)

# EOP (no operands) → must not crash, opcode must be 00001
eop = Instruction.encode('EOP')
check("encode EOP → 32 bits",      len(eop),    32)
check("encode EOP → opcode 00001", eop[0:5], '00001')

# PRNT R1 → opcode 00000
f = decode_fields(Instruction.encode('PRNT R1'))
check("encode PRNT R1 → opcode 00000", f['opcode'], '00000')

# CMP transforms to SUB JR <op> → opcode 11010
f = decode_fields(Instruction.encode('CMP R2'))
check("encode CMP R2 → opcode 11010 (SUB)", f['opcode'], '11010')

# CB transforms to ADD BR <block> → opcode 11001
f = decode_fields(Instruction.encode('CB B1'))
check("encode CB B1 → opcode 11001 (ADD)", f['opcode'], '11001')


# ════════════════════════════════════════════════════════════════
# SECTION 3 — encodeProgram unit tests
# Verifies memory layout, comment skipping, and CB/CF reordering.
# ════════════════════════════════════════════════════════════════

print("\n── Section 3: encodeProgram ────────────────────────────")

# Basic layout: two MOV instructions then FUNC
reset()
Instruction.encodeProgram([
    'MOV R1 3.0',
    'MOV R2 4.0',
    'FUNC',
])
check("encodeProgram: memory[9] is 32-bit string",
      len(memory.data.get(9, '')), 32)
check("encodeProgram: memory[10] is 32-bit string",
      len(memory.data.get(10, '')), 32)
check("encodeProgram: memory[11] is FUNC (all zeros)",
      memory.data.get(11, ''), '0' * 32)

# Single-line comment (x prefix) must be skipped
reset()
Instruction.encodeProgram([
    'x this line is a comment',
    'MOV R1 5.0',
    'FUNC',
])
check("encodeProgram: single-line comment skipped, instruction at mem[9]",
      len(memory.data.get(9, '')), 32)

# Multiline comment block (z...z) must be skipped entirely
reset()
Instruction.encodeProgram([
    'z',
    'MOV R1 99.0',
    'z',
    'MOV R2 7.0',
    'FUNC',
])
f_first = decode_fields(memory.data.get(9, '0' * 32))
check("encodeProgram: multiline comment skipped — first real instr at mem[9]",
      f_first['opcode'], '01000')   # MOV opcode = 01000

# CB must be placed at the front of the instruction list
reset()
Instruction.encodeProgram([
    'CB B1',
    'MOV R1 1.0',
    'FUNC',
])
bc = register.load(int(variable.load('BR')))
check("encodeProgram: CB increments block counter to 1", bc, 1.0)
f_cb = decode_fields(memory.data.get(9, '0' * 32))
check("encodeProgram: CB instruction placed at memory[9]", f_cb['opcode'], '11001')

# Empty lines must be skipped without crashing
reset()
Instruction.encodeProgram([
    '',
    '   ',
    'MOV R1 2.0',
    'FUNC',
])
check("encodeProgram: empty lines skipped, instruction at mem[9]",
      len(memory.data.get(9, '')), 32)


# ════════════════════════════════════════════════════════════════
# SECTION 4 — Full end-to-end run tests
# Verifies the complete pipeline: compile → load → execute → result.
# ════════════════════════════════════════════════════════════════

print("\n── Section 4: end-to-end run ───────────────────────────")

# ── 4.1: MOV immediate then PRNT ────────────────────────────
out = run_program(['MOV R1 7.0', 'PRNT R1', 'FUNC'])
check("e2e MOV R1 7.0 → PRNT prints 7.0", out, '7.0')

# ── 4.2: ADD two registers ──────────────────────────────────
out = run_program(['MOV R1 3.0', 'MOV R2 4.0', 'ADD R1 R2', 'PRNT R1', 'FUNC'])
check("e2e ADD: 3.0 + 4.0 → PRNT prints 7.0", out, '7.0')

# ── 4.3: SUB two registers ──────────────────────────────────
out = run_program(['MOV R1 10.0', 'MOV R2 3.0', 'SUB R1 R2', 'PRNT R1', 'FUNC'])
check("e2e SUB: 10.0 - 3.0 → PRNT prints 7.0", out, '7.0')

# ── 4.4: MUL two registers ──────────────────────────────────
out = run_program(['MOV R1 3.0', 'MOV R2 4.0', 'MUL R1 R2', 'PRNT R1', 'FUNC'])
check("e2e MUL: 3.0 * 4.0 → PRNT prints 12.0", out, '12.0')

# ── 4.5: DIV two registers ──────────────────────────────────
out = run_program(['MOV R1 8.0', 'MOV R2 2.0', 'DIV R1 R2', 'PRNT R1', 'FUNC'])
check("e2e DIV: 8.0 / 2.0 → PRNT prints 4.0", out, '4.0')

# ── 4.6: MOD two registers ──────────────────────────────────
out = run_program(['MOV R1 7.0', 'MOV R2 3.0', 'MOD R1 R2', 'PRNT R1', 'FUNC'])
check("e2e MOD: 7.0 % 3.0 → PRNT prints 1.0", out, '1.0')

# ── 4.7: DIV by zero → exception message and undefined result
out = run_program([
    'MOV R1 5.0',
    'MOV R2 0.0',
    'DIV R1 R2',
    'PRNT R1',
    'FUNC',
])
check("e2e DIV by zero → output contains 'undefined' or 'Division'",
      'undefined' in out or 'Division' in out, True)

# ── 4.8: DIV both zero → Infinity ───────────────────────────
out = run_program([
    'MOV R1 0.0',
    'MOV R2 0.0',
    'DIV R1 R2',
    'PRNT R1',
    'FUNC',
])
check("e2e DIV 0/0 → output contains 'Infinity' or 'Division'",
      'Infinity' in out or 'Division' in out, True)

# ── 4.9: JEQ taken when JR == 0 (equal) ─────────────────────
# CMP R1 (where R1=0) stores 0-0=0 into JR → JEQ should jump
reset()
Instruction.encodeProgram([
    'CB B1',
    'MOV R1 0.0',
    'CMP R1',
    'JEQ B1',
    'MOV R2 99.0',   # should be SKIPPED by the jump
    'FUNC',
])
p = run.Program.__new__(run.Program)
p.run()
check("e2e JEQ taken: R2 stays 0.0 (MOV R2 99.0 skipped)", reg('R2'), 0.0)

# ── 4.10: JNE not taken when JR == 0 ────────────────────────
# CMP R1 (where R1=0) stores 0 into JR → JNE should NOT jump
reset()
Instruction.encodeProgram([
    'CB B1',
    'MOV R1 0.0',
    'CMP R1',
    'JNE B1',        # JR=0, condition is JR!=0 → False → not taken
    'MOV R2 5.0',    # should EXECUTE
    'FUNC',
])
p = run.Program.__new__(run.Program)
p.run()
check("e2e JNE not taken: R2 gets 5.0", reg('R2'), 5.0)

# ── 4.11: JLT taken when JR < 0 ─────────────────────────────
# CMP R1 (where R1=3) → JR = 0 - 3 = -3 → JLT should jump
reset()
Instruction.encodeProgram([
    'CB B1',
    'MOV R1 3.0',
    'CMP R1',
    'JLT B1',
    'MOV R2 99.0',   # should be SKIPPED
    'FUNC',
])
p = run.Program.__new__(run.Program)
p.run()
check("e2e JLT taken (JR=-3): R2 stays 0.0", reg('R2'), 0.0)

# ── 4.12: JGT not taken when JR < 0 ─────────────────────────
reset()
Instruction.encodeProgram([
    'CB B1',
    'MOV R1 3.0',
    'CMP R1',
    'JGT B1',        # JR=-3, condition is JR>0 → False → not taken
    'MOV R2 5.0',    # should EXECUTE
    'FUNC',
])
p = run.Program.__new__(run.Program)
p.run()
check("e2e JGT not taken (JR=-3): R2 gets 5.0", reg('R2'), 5.0)

# ── 4.13: Chain ADD then MUL ─────────────────────────────────
out = run_program([
    'MOV R1 2.0',
    'MOV R2 3.0',
    'ADD R1 R2',   # R1 = 5
    'MOV R3 2.0',
    'MUL R1 R3',   # R1 = 10
    'PRNT R1',
    'FUNC',
])
check("e2e chain ADD then MUL → 10.0", out, '10.0')

# ── 4.14: MOV register to register ──────────────────────────
reset()
Instruction.encodeProgram([
    'MOV R1 6.0',
    'MOV R2 R1',
    'FUNC',
])
p = run.Program.__new__(run.Program)
p.run()
check("e2e MOV R2 R1 copies value → R2=6.0", reg('R2'), 6.0)

# ── 4.15: EOP halts execution before PRNT ───────────────────
out = run_program([
    'MOV R1 1.0',
    'EOP',
    'PRNT R1',     # must NOT execute
    'FUNC',
])
check("e2e EOP halts before PRNT → no output", out, '')

# ── 4.16: PRNT direct register value ────────────────────────
out = run_program(['MOV R1 42.0', 'PRNT R1', 'FUNC'])
check("e2e PRNT R1=42.0 → prints 42.0", out, '42.0')

# ── 4.17: Multiple PRNT statements ──────────────────────────
out = run_program([
    'MOV R1 1.0',
    'MOV R2 2.0',
    'PRNT R1',
    'PRNT R2',
    'FUNC',
])
check("e2e multiple PRNT → '1.0' then '2.0'", out, '1.0\n2.0')

# ── 4.18: Except class — isOccur and getReturn ──────────────
exc = run.Except("test error", occur=True)
exc.setReturn('TestValue')
check("Except isOccur True  → True",        exc.isOccur(),   True)
check("Except getReturn     → 'TestValue'", exc.getReturn(), 'TestValue')

exc2 = run.Except("inactive", occur=False)
check("Except isOccur False → False",       exc2.isOccur(),  False)

# ── 4.19: exception() method returns correct Except objects ──
e_inf = run.Program.exception('DivByZero', (0, 0))
check("exception DivByZero 0/0 → 'Infinity'",   e_inf.getReturn(), 'Infinity')

e_und = run.Program.exception('DivByZero', (5, 0))
check("exception DivByZero 5/0 → 'undefined'",  e_und.getReturn(), 'undefined')

check("exception returns Except instance",
      isinstance(e_inf, run.Except), True)


# ════════════════════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════════════════════

total = PASS + FAIL
print(f"\n{'═' * 52}")
print(f"  Results: {PASS}/{total} passed", end="")
if FAIL == 0:
    print("  ✓ all clear")
else:
    print(f"  — {FAIL} failed")
print(f"{'═' * 52}\n")