# Filename: addressing.py
# This file contains a Access class for easy acces of memory and register and AddressingMode class.

from storage import memory, register, variable
from bin_convert import HalfPrecision

class Access:

    @staticmethod
    def data(addr, flow):
        """
        Loads data by following the specified storage flow.

        Example:
        data("PC", ["var", "reg"])

        Flow:
        variable["PC"] -> register[address]
        """

        current = addr

        for f in flow:

            # Access variable storage
            if f == "var":
                current = variable.load(current)

            # Access register storage
            elif f == "reg":
                current = register.load(current)

            # Access memory storage
            elif f == "mem":
                current = memory.load(current)

        return current

    @staticmethod
    def store(typ, addr, value):
        """
        Stores value into either register or memory.
        """

        # Store to register
        if typ == "reg":
            register.store(addr, value)

        # Store to memory
        elif typ == "mem":
            memory.store(addr, value)

class AddressingMode:

    @staticmethod
    def immediate(var):
        """
        Immediate addressing mode.

        Converts HalfPrecision binary format
        into decimal value.
        """

        return HalfPrecision.hpbin2dec(var)

    @staticmethod
    def relative(displace):
        """
        Relative addressing mode.

        Effective Address:
        PC + displacement
        """

        pc = Access.data("PC", ["var", "reg"])

        eff_addr = int(pc + displace)

        value = memory.load(eff_addr)

        return value

    @staticmethod
    def based(displace):
        """
        Based addressing mode.

        Effective Address:
        BR + displacement
        """

        br = Access.data("BR", ["var", "reg"])

        eff_addr = int(br + displace)

        value = memory.load(eff_addr)

        return value

    @staticmethod
    def indexed(displace):
        """
        Indexed addressing mode.

        Effective Address:
        XR + displacement
        """

        xr = Access.data("XR", ["var", "reg"])

        eff_addr = int(xr + displace)

        value = memory.load(eff_addr)

        return eff_addr, value

    @staticmethod
    def register(reg_addr):
        """
        Register addressing mode.

        Returns:
        effective address,
        value,
        storage type
        """

        # Convert HalfPrecision binary to decimal if needed
        if type(reg_addr) == str:
            reg_addr = HalfPrecision.hpbin2dec(reg_addr)

        reg_addr = int(reg_addr)

        value = register.load(reg_addr)

        return reg_addr, value, "reg"

    @staticmethod
    def register_indirect(reg_addr):
        """
        Register indirect addressing mode.

        The register contains the memory address.
        """

        # Convert HalfPrecision binary to decimal if needed
        if type(reg_addr) == str:
            reg_addr = HalfPrecision.hpbin2dec(reg_addr)

        reg_addr = int(reg_addr)

        # Get memory address from register
        mem_addr = int(register.load(reg_addr))

        # Get value from memory
        value = memory.load(mem_addr)

        return mem_addr, value

    @staticmethod
    def direct(var_addr):
        """
        Direct addressing mode.

        Uses memory address directly.
        """

        # Convert HalfPrecision binary to decimal if needed
        if type(var_addr) == str:
            var_addr = HalfPrecision.hpbin2dec(var_addr)

        var_addr = int(var_addr)

        value = memory.load(var_addr)

        return var_addr, value

    @staticmethod
    def indirect(var_addr):
        """
        Indirect addressing mode.

        Memory contains another memory address.
        """

        # Convert HalfPrecision binary to decimal if needed
        if type(var_addr) == str:
            var_addr = HalfPrecision.hpbin2dec(var_addr)

        var_addr = int(var_addr)

        # Get effective address from memory
        eff_addr = int(memory.load(var_addr))

        # Get actual value from effective address
        value = memory.load(eff_addr)

        return eff_addr, value

    @staticmethod
    def autoinc(reg_addr):
        """
        Auto-increment addressing mode.

        Uses register value as memory address,
        then increments register by 1.
        """

        # Convert HalfPrecision binary to decimal if needed
        if type(reg_addr) == str:
            reg_addr = HalfPrecision.hpbin2dec(reg_addr)

        reg_addr = int(reg_addr)

        # Get memory address from register
        mem_addr = int(register.load(reg_addr))

        # Load value from memory
        value = memory.load(mem_addr)

        # Increment register
        register.store(reg_addr, mem_addr + 1)

        return mem_addr, value

    @staticmethod
    def autodec(reg_addr):
        """
        Auto-decrement addressing mode.

        Decrements register by 1 first,
        then uses the updated value
        as memory address.
        """

        # Convert HalfPrecision binary to decimal if needed
        if type(reg_addr) == str:
            reg_addr = HalfPrecision.hpbin2dec(reg_addr)

        reg_addr = int(reg_addr)

        # Decrement register value
        mem_addr = int(register.load(reg_addr) - 1)

        register.store(reg_addr, mem_addr)

        # Load value from memory
        value = memory.load(mem_addr)

        return mem_addr, value