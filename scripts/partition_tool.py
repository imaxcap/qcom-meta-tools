#!/usr/bin/env python3
import getopt
import struct
import sys


TABLE_SIZE = 912
TABLE_HEADER_SIZE = 16
ENTRY_SIZE = 28
MAX_PARTITIONS = 32


def crc32_mpeg2(data, crc=0):
    """Qualcomm MIBIB CRC: CRC-32/MPEG-2, chained with an initial value."""
    for byte in data:
        crc ^= byte << 24
        for _ in range(8):
            if crc & 0x80000000:
                crc = ((crc << 1) ^ 0x04C11DB7) & 0xFFFFFFFF
            else:
                crc = (crc << 1) & 0xFFFFFFFF
    return crc

def usage():
    print("Usage: partition_tool.py [-s page_size -p pages_per_block -b block_count] "
          "[-x secondary_page_size -y secondary_pages_per_block "
          "-z secondary_block_count] [-c mibib_copies] "
          "-u usr_tbl_fname -o sys_tbl_fname")
    sys.exit(1)

def main():
    page_size = 0
    pages_per_block = 0
    block_count = 0
    secondary_page_size = 0
    secondary_pages_per_block = 0
    secondary_block_count = 0
    mibib_copies = 2
    usr_tbl_fname = None
    sys_tbl_fname = None

    try:
        opts, args = getopt.getopt(sys.argv[1:], "s:p:b:x:y:z:c:u:o:")
    except getopt.GetoptError:
        usage()

    for opt, arg in opts:
        if opt == "-s":
            page_size = int(arg)
        elif opt == "-p":
            pages_per_block = int(arg)
        elif opt == "-b":
            block_count = int(arg)
        elif opt == "-x":
            secondary_page_size = int(arg)
        elif opt == "-y":
            secondary_pages_per_block = int(arg)
        elif opt == "-z":
            secondary_block_count = int(arg)
        elif opt == "-c":
            mibib_copies = int(arg)
        elif opt == "-u":
            usr_tbl_fname = arg
        elif opt == "-o":
            sys_tbl_fname = arg

    if not usr_tbl_fname or not sys_tbl_fname:
        usage()

    if page_size == 0 or pages_per_block == 0:
        print("Invalid device geometry infomation")
        sys.exit(1)

    sys_pages = (TABLE_SIZE + page_size - 1) // page_size
    user_pages = sys_pages
    pages_used = 1 + sys_pages + user_pages + 1
    if pages_per_block < pages_used or mibib_copies < 1:
        print("Invalid device geometry infomation")
        sys.exit(1)

    block_sizes_kb = {
        0: max(1, page_size * pages_per_block // 1024),
    }
    block_counts = {0: block_count}
    if secondary_page_size and secondary_pages_per_block:
        block_sizes_kb[1] = max(
            1, secondary_page_size * secondary_pages_per_block // 1024)
        block_counts[1] = secondary_block_count

    try:
        with open(usr_tbl_fname, "rb") as f:
            usr_data = f.read()
    except IOError:
        print("open usr partition table file failed")
        sys.exit(1)

    if len(usr_data) < TABLE_SIZE:
        print("reading user partition table file failed")
        sys.exit(1)

    usr_data = usr_data[:TABLE_SIZE]
    usr_magic1, usr_magic2, usr_version, numparts = struct.unpack("<IIII", usr_data[:16])

    if numparts > MAX_PARTITIONS:
        print("Problem in usr to sys parti conversion")
        sys.exit(1)

    sys_entries = bytearray()
    curr_offsets = {0: 0, 1: 0}

    for i in range(numparts):
        entry_data = usr_data[16 + i * 28 : 16 + (i + 1) * 28]
        name, img_size, padding, which_flash, attr1, attr2, attr3, attr4 = \
            struct.unpack("<16sIHHBBBB", entry_data)

        if which_flash not in block_sizes_kb:
            print("Problem in usr to sys parti conversion")
            sys.exit(1)

        block_size_kb = block_sizes_kb[which_flash]

        # size_block entries carry their size directly in erase blocks and use
        # the legacy GROW marker. size_kb entries must be rounded up.
        if attr4 == 0xFE:
            length = img_size + padding
        else:
            length = (img_size + padding + block_size_kb - 1) // block_size_kb

        offset = curr_offsets[which_flash]
        curr_offsets[which_flash] += length

        block_limit = block_counts.get(which_flash, 0)
        if block_limit and curr_offsets[which_flash] > block_limit:
            print("Problem in usr to sys parti conversion")
            sys.exit(1)

        sys_entry = struct.pack(
            "<16sIIBBBB", name, offset, length, attr1, attr2, attr3,
            which_flash)
        sys_entries += sys_entry

    remaining_entries = MAX_PARTITIONS - numparts
    if remaining_entries > 0:
        sys_entries += b'\x00' * (remaining_entries * 28)

    sys_table_header = struct.pack("<IIII", 0x55EE73AA, 0xE35EBDDB, usr_version, numparts)
    sys_table = sys_table_header + sys_entries

    total_binary = bytearray()

    for copy_idx in range(mibib_copies):
        # Page 0
        page0_header = struct.pack("<IIII", 0xFE569FAC, 0xCD7F127A, 4, copy_idx)
        page0_data = page0_header + b'\xFF' * (page_size - 16)

        # System and user tables may span multiple pages on NOR geometries.
        sys_data = sys_table + b'\xFF' * (sys_pages * page_size - len(sys_table))

        user_data = usr_data + b'\xFF' * (user_pages * page_size - len(usr_data))

        # CRC of the three complete, padded regions above. Qualcomm's
        # implementation chains the CRC across each page with an initial 0.
        crc_val = crc32_mpeg2(page0_data)
        crc_val = crc32_mpeg2(sys_data, crc_val)
        crc_val = crc32_mpeg2(user_data, crc_val)

        crc_page_header = struct.pack("<IIII", 0x9D41BEA1, 0xF1DED2EA, 1, crc_val)
        crc_page_data = crc_page_header + b'\xFF' * (page_size - 16)

        # Remaining pages in block
        remaining_pages_count = pages_per_block - pages_used
        remaining_data = b'\xFF' * (remaining_pages_count * page_size)

        block_data = page0_data + sys_data + user_data + crc_page_data + remaining_data
        total_binary += block_data

    with open(sys_tbl_fname, "wb") as f:
        f.write(total_binary)

if __name__ == "__main__":
    main()
