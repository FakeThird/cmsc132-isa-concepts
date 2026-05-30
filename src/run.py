# Filename: run.py
# This file contains two classes. The Except class handles the exception while the Program class
# runs the Instruction Codes from the memory pointed by 'PC'.

from storage import memory, register, variable
from addressing import Access, AddressingMode
from bin_convert import HalfPrecision, Length
from compiler import Instruction


# ─────────────────────────────────────────────────────────────
# Class: Except
# ─────────────────────────────────────────────────────────────

class Except:

    def __init__(self, msg, occur=True):
        """
        Initialize the exception.

        Parameters:
            msg   : The message of the exception.
            occur : Whether the exception has occurred (default True).
        """
        self.message = msg
        self.occur   = occur    #since there is a global checker if the exception has occurred, this is used to set the return value of the exception when it occurs
        self.ret     = None     #the return value of the exception, which can be set when the exception is created or when it occurs

    def dispMSG(self):
        """Print the exception message."""
        print(self.message)

    def isOccur(self):
        """Return True if the exception occurred, otherwise False."""
        return self.occur

    def setReturn(self, value):
        """Set the return value of the exception."""
        self.ret = value

    def getReturn(self):
        """Return the return value of the exception."""
        return self.ret


# ─────────────────────────────────────────────────────────────
# Class: Program
# ─────────────────────────────────────────────────────────────

class Program:

    def __init__(self, program):
        """
        Encode every instruction of the program into memory.

        Parameters:
            program : List of raw instruction strings read from the .isa file.
        """
        Instruction.encodeProgram(program) # Encodes the program and stores instructions in memory

    @staticmethod
    def exception(name, value):
        """
        Return an Except object for a named exception.

        Currently handles 'DivByZero':
            - Both operands zero  → return value is 'Infinity'
            - Only operand 2 zero → return value is 'undefined'

        Parameters:
            name  : Exception name string (e.g. 'DivByZero').
            value : Tuple (op1, op2) involved in the exception.

        Returns:
            An Except instance with the return value already set.
        """
        if name == 'DivByZero':
            exc = Except("Division by zero error.")
            if value[0] == 0 and value[1] == 0:
                exc.setReturn('Infinity')
            else:
                exc.setReturn('undefined')
            return exc

    def execute(self, result, opcode):
        """
        Perform the Execute operation described by opcode.

        If Write Bit = 1 → arithmetic (MOD/ADD/SUB/MUL/DIV).
        If Write Bit = 0 → jump comparison against JR and zero.

        Parameters:
            result : Tuple (op1_value, op2_value).
            opcode : 5-bit opcode string from the instruction.

        Returns:
            Arithmetic result (Write=1) or boolean jump decision (Write=0).
        """
        write_bit = int(opcode[1]) # Write Bit is the second bit of the opcode
        category  = int(opcode[2:5], 2) # Category code is the last 3 bits of the opcode

        op1, op2 = result

        if write_bit == 1:
            # Arithmetic operations, keyed by category code
            if category == 0:    # MOD
                return op1 % op2
            elif category == 1:  # ADD
                return op1 + op2
            elif category == 2:  # SUB
                return op1 - op2
            elif category == 3:  # MUL
                return op1 * op2
            elif category == 4:  # DIV — handle division by zero
                if op2 == 0:
                    exc = Program.exception('DivByZero', (op1, op2))
                    exc.dispMSG()
                    return exc.getReturn()
                return op1 / op2

        else: #if second bit of opcode is 0, then it's a jump operation, which compares JR against zero using the category code to determine the type of comparison
            # Jump operations compare JR against zero
            jr = Access.data("JR", ["var", "reg"])
            if category == 0:    # JEQ
                return jr == 0
            elif category == 1:  # JNE
                return jr != 0
            elif category == 2:  # JLT
                return jr < 0
            elif category == 3:  # JLE
                return jr <= 0
            elif category == 4:  # JGT
                return jr > 0
            elif category == 5:  # JGE
                return jr >= 0
            elif category == 6:  # JMP (unconditional)
                return True

    def write(self, dest, src, movecode):
        """
        Perform the Write operation.

        movecode semantics:
            1 = CALL  → copy PC to CR first, then move src to dest
            2 = RET   → copy CR to PC first, then move src to dest
            3 = SCAN  → replace src with user input, then move to dest
            0 (or any other value) = plain MOV, move src to dest

        Parameters:
            dest     : Tuple (effective_address, storage_type).
            src      : Source value to write.
            movecode : Integer indicating the move type.
        """
        if movecode == 1:
            # CALL: save current PC into CR before the jump
            pc_val  = Access.data("PC", ["var", "reg"]) # Get current PC value from register or variable storage
            cr_addr = int(variable.load("CR"))          #load CR address from variable storage
            register.store(cr_addr, pc_val)             #store current PC value into CR address in register storage

        elif movecode == 2:
            # RET: restore PC from CR before the return
            cr_val  = Access.data("CR", ["var", "reg"])
            pc_addr = int(variable.load("PC"))
            register.store(pc_addr, cr_val)

        elif movecode == 3:
            # SCAN: print the associated message then read user input
            msg_dict = variable.data.get("MSG", {})
            scan_idx  = variable.data.get("SI", 0)
            if scan_idx in msg_dict:
                print(msg_dict[scan_idx], end="")
            variable.data["SI"] = scan_idx + 1  # Increment message index for next SCAN
            src = float(input())  # Read user input as a float (could be int or HP, but float is more general)

        # Default move: src → dest (always performed)
        dest_addr, dest_type = dest
        Access.store(dest_type, dest_addr, src)

    def getOp(self, inscode):
        """
        Decode a 10-bit operand code and call the correct AddressingMode.

        encodeOp() in compiler.py produces: [4-bit mode][6-bit addr] = 10 bits.
        The instruction stores:             [3-bit mode][7-bit addr] = 10 bits.
        encode() in compiler.py uses raw[0:3] as mode and raw[3:10] as addr,
        so the 4th mode bit is already folded into the leading addr bit.

        Therefore getOp reads:
            mode = inscode[0:3]   (3 bits, matches Op1Mode / Op2Mode in instruction)
            addr = inscode[3:]    (7 bits, includes displacement-type flag as MSB)

        Parameters:
            inscode : 10-bit binary string (mode + addr) from the instruction.

        Returns:
            The return value of the matching AddressingMode static method.
        """
        mode_bits = inscode[0:3]
        addr_bits = inscode[3:]     # 7 bits; MSB is displacement-type flag for indexed

        mode = int(mode_bits, 2)

        # Resolve displacement for indexed modes (addr_bits[0] = type flag)
        def get_reg_or_mem_displace():
            disp_type = int(addr_bits[0])    # 0 = register, 1 = memory
            disp_addr = int(addr_bits[1:], 2)
            if disp_type == 0:
                return register.load(disp_addr)
            else:
                return memory.load(disp_addr)

        if mode == 0:    # Register
            addr = int(addr_bits, 2)
            return AddressingMode.register(int(addr))

        elif mode == 1:  # Register Indirect
            addr = int(addr_bits, 2)
            return AddressingMode.register_indirect(int(addr))

        elif mode == 2:  # Direct
            addr = int(addr_bits, 2)
            return AddressingMode.direct(int(addr))

        elif mode == 3:  # Indirect
            addr = int(addr_bits, 2)
            return AddressingMode.indirect(int(addr))

        elif mode == 4:  # Indexed — displacement from register or memory
            displace = get_reg_or_mem_displace()
            return AddressingMode.indexed(displace)

        elif mode == 5:  # Indexed — integer displacement (sign bit in addr_bits[0])
            sign     = int(addr_bits[0])
            mag      = int(addr_bits[1:], 2)
            displace = -mag if sign else mag
            return AddressingMode.indexed(displace)

        elif mode == 6:  # Auto-Increment
            addr = int(addr_bits, 2)
            return AddressingMode.autoinc(int(addr))

        elif mode == 7:  # Auto-Decrement
            addr = int(addr_bits, 2)
            return AddressingMode.autodec(int(addr))

    def getOp2(self, inscode, ib, rb, extra_bits):
        """
        Decode operand 2, accounting for the ib and rb flags.

        Parameters:
            inscode    : 10-bit binary string (Op2Mode + Op2Addr).
            ib         : Immediate bit (int). 1 = immediate mode.
            rb         : Relative bit (int). 1 = relative or based mode.
            extra_bits : 5-bit string from bits 27-31 of the instruction.

        Returns:
            The decoded value of operand 2.
        """
        if ib == 1:
            hp_reconstructed = '0' + inscode + extra_bits   # 1 + 10 + 5 = 16 bits for the immediate HP value
            return AddressingMode.immediate(hp_reconstructed)

        mode_bits = inscode[0:3]
        addr_bits = inscode[3:]
        mode      = int(mode_bits, 2)

        if rb == 1:
            disp = int(addr_bits[1:], 2)
           
            if mode == 0:    # Based, displacement from register
                return AddressingMode.based(register.load(int(disp)))
            elif mode == 1:  # Based, displacement from memory
                return AddressingMode.based(memory.load(int(disp)))
            elif mode == 2:  # Based, positive integer displacement
                return AddressingMode.based(disp)
            elif mode == 3:  # Based, negative integer displacement
                return AddressingMode.based(-disp)
            elif mode == 4:  # Relative, displacement from register
                return AddressingMode.relative(register.load(int(disp)))
            elif mode == 5:  # Relative, displacement from memory
                return AddressingMode.relative(memory.load(int(disp)))
            elif mode == 6:  # Relative, positive integer displacement
                return AddressingMode.relative(disp)
            elif mode == 7:  # Relative, negative integer displacement
                return AddressingMode.relative(-disp)

        # Standard modes (same logic as getOp)
        return self.getOp(inscode)

    def run(self):
        """
        The main CPU loop. Each iteration:
            1. Load the address held in IR, fetch the instruction at that address.
            2. Break if the instruction is not 32 bits or is all zeros.
            3. Split into opcode, op1 code, op2 code.
            4. If Execute Bit = 1, call execute().
            5. If Write Bit = 1, call write().
            6. If both bits = 0, print.
            7. Copy PC to IR, then increment PC by 1.
        """
        variable.data["SI"] = 0  # Initialize Scan Index for SCAN messages

        monadic = []   # reserved for future monadic operations
        niladic = []   # reserved for future niladic operations

        while True:

            # ── 1. Fetch ──────────────────────────────────────
            ir_val  = Access.data("IR", ["var", "reg"])
            ir_addr = int(ir_val)

            # Load the raw 32-bit instruction string directly from memory.data
            # (memory.load() converts HP values; we need the raw binary string.)
            raw_instr = memory.data.get(ir_addr, None)

            # Break if instruction is missing, not 32 bits, or all zeros
            if (raw_instr is None
                    or not isinstance(raw_instr, str)
                    or len(raw_instr) != Length.instrxn
                    or raw_instr == '0' * Length.instrxn):
                break

            # ── 2. Decode ─────────────────────────────────────
            #  bits  0– 4 : opcode  (5 bits)
            #  bit   5    : ib      (1 bit, immediate)
            #  bits  6– 8 : op1mode (3 bits)
            #  bits  9–15 : op1addr (7 bits)
            #  bit  16    : rb      (1 bit, relative/based)
            #  bits 17–19 : op2mode (3 bits)
            #  bits 20–26 : op2addr (7 bits)
            #  bits 27–31 : extra   (5 bits)

            opcode    = raw_instr[0:5]
            ib        = int(raw_instr[5])
            op1code   = raw_instr[6:16]    # 3-bit mode + 7-bit addr
            rb        = int(raw_instr[16])
            op2code   = raw_instr[17:27]   # 3-bit mode + 7-bit addr
            extra     = raw_instr[27:32]   # 5 extra bits (tail of immediate HP value)

            execute_bit = int(opcode[0])
            write_bit   = int(opcode[1])

            if opcode == '00001':
                # Special case for HALT (opcode '00001'): break immediately
                break

            # ── 3. Get Operand 1 ──────────────────────────────
            op1_result = self.getOp(op1code)

            if isinstance(op1_result, tuple) and len(op1_result) == 3:
                op1_addr, op1_val, op1_type = op1_result   # register mode
            elif isinstance(op1_result, tuple) and len(op1_result) == 2:
                op1_addr, op1_val = op1_result
                op1_type = "mem"
            else:
                op1_val  = op1_result
                op1_addr = None
                op1_type = None

            # ── 4. Get Operand 2 ──────────────────────────────
            op2_val = None
            if opcode not in niladic and opcode not in monadic:
                op2_result = self.getOp2(op2code, ib, rb, extra)

                if isinstance(op2_result, tuple) and len(op2_result) == 3:
                    _, op2_val, _ = op2_result
                elif isinstance(op2_result, tuple) and len(op2_result) == 2:
                    _, op2_val = op2_result
                else:
                    op2_val = op2_result

            # ── 5. Execute ────────────────────────────────────
            exec_result = None
            jumped      = False

            if execute_bit == 1:
                exec_result = self.execute((op1_val, op2_val), opcode)

                # Jump operations: if condition is True, redirect PC to op1's address
                if write_bit == 0 and exec_result:
                    pc_addr = int(variable.load("PC"))
                    register.store(pc_addr, op1_val)
                    ir_reg  = int(variable.load("IR"))
                    register.store(ir_reg, op1_val)
                    jumped = True

            # ── 6. Write ──────────────────────────────────────
            movecode = 0  

            if write_bit == 1:
                if execute_bit == 0:
                    category = int(opcode[2:5], 2)
                    # Map category to movecode: MOV=0, CALL=1, RET=2, SCAN=3
                    movecode_map = {0: 0, 1: 1, 2: 2, 3: 3}
                    movecode = movecode_map.get(category, 0)

                # Source is the execute result for arithmetic; op2 for plain moves
                src  = exec_result if execute_bit == 1 else op2_val
                dest = (op1_addr, op1_type)
                self.write(dest, src, movecode)

            # ── Print (execute=0, write=0) ────────────────────
            elif execute_bit == 0 and write_bit == 0:
                category = int(opcode[2:5], 2)
                if category == 0:   # PRNT
                    print(op1_val)

            # ── 7. Advance PC and IR (unless we just jumped) ──
            if not jumped:
                pc_addr = int(variable.load("PC"))
                pc_val  = register.load(pc_addr)
                register.store(pc_addr, pc_val + 1)

                ir_reg = int(variable.load("IR"))
                register.store(ir_reg, pc_val + 1)


# ─────────────────────────────────────────────────────────────
# File-loading block
# ─────────────────────────────────────────────────────────────

import os

# Create the global DivByZero exception (not yet occurred)
DivByZero = Except("Division by zero.", occur=False)


# Locate the .isa file (extension matches the group shortcut)
isa_file = None
for fname in os.listdir("."):
    if fname.endswith(".isa"):
        isa_file = fname
        break

if isa_file:
    with open(isa_file, "r") as f:
        program = f.read().splitlines()

    p = Program(program)
    p.run()
else:
    print("No .isa file found. Please provide a file with your group's extension.")