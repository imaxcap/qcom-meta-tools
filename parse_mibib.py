#!/usr/bin/env python3
import sys
import os
import struct
import argparse
import xml.etree.ElementTree as ET
import xml.dom.minidom

SYS_TABLE_MAGIC1 = 0x55EE73AA
SYS_TABLE_MAGIC2 = 0xE35EBDDB
USR_TABLE_MAGIC1 = 0xAA7D1B9A
USR_TABLE_MAGIC2 = 0x1F7D48BC

def parse_mibib_bin(bin_path):
    """
    Parses Qualcomm MIBIB binary (nand-system-partition-*.bin / norplusnand-system-partition-*.bin)
    and returns a structured dict of partition entries.
    """
    with open(bin_path, 'rb') as f:
        data = f.read()

    # Search for System Table Magic 0x55EE73AA (little-endian \xaa\x73\xee\x55)
    sys_offset = data.find(b'\xaa\x73\xee\x55')
    if sys_offset == -1:
        raise ValueError(f"Could not find System Partition Table magic (0x55EE73AA) in '{bin_path}'")

    magic1, magic2, version, numparts = struct.unpack('<IIII', data[sys_offset:sys_offset + 16])

    entries = []
    for i in range(numparts):
        entry_data = data[sys_offset + 16 + i * 28 : sys_offset + 16 + (i + 1) * 28]
        name_b, offset, length, attr1, attr2, attr3, which_flash = struct.unpack('<16sIIBBBB', entry_data)
        name = name_b.rstrip(b'\x00').decode('ascii', errors='ignore')

        # Ensure which_flash is strictly 0 (NOR/primary) or 1 (NAND/secondary)
        which_flash_val = 1 if which_flash != 0 else 0

        entries.append({
            'name': name,
            'offset': offset,
            'length': length,
            'which_flash': which_flash_val,
            'attr1': attr1,
            'attr2': attr2,
            'attr3': attr3,
        })

    return {
        'version': version,
        'numparts': numparts,
        'entries': entries
    }

def export_to_xml(mibib_info, output_xml_path):
    """
    Exports parsed MIBIB partition information to Qualcomm XML format.
    """
    root = ET.Element('partition_table')
    
    magic_elem = ET.SubElement(root, 'magic_numbers')
    usr_m1 = ET.SubElement(magic_elem, 'usr_part_magic1')
    usr_m1.text = '0xAA7D1B9A'
    usr_m2 = ET.SubElement(magic_elem, 'usr_part_magic2')
    usr_m2.text = '0x1F7D48BC'

    ver_elem = ET.SubElement(root, 'partition_version', attrib={'length': '4'})
    ver_elem.text = hex(mibib_info['version'])

    parts_elem = ET.SubElement(root, 'partitions')

    for entry in mibib_info['entries']:
        part_elem = ET.SubElement(parts_elem, 'partition')
        
        name_e = ET.SubElement(part_elem, 'name', attrib={'length': '16', 'type': 'string'})
        name_e.text = entry['name']

        offset_e = ET.SubElement(part_elem, 'offset', attrib={'length': '4'})
        offset_e.text = str(entry['offset'])

        len_e = ET.SubElement(part_elem, 'length', attrib={'length': '4'})
        len_e.text = str(entry['length'])

        wf_e = ET.SubElement(part_elem, 'which_flash', attrib={'length': '2'})
        wf_e.text = str(entry['which_flash'])

        a1_e = ET.SubElement(part_elem, 'attr')
        a1_e.text = f"0x{entry['attr1']:02X}"

        a2_e = ET.SubElement(part_elem, 'attr')
        a2_e.text = f"0x{entry['attr2']:02X}"

        a3_e = ET.SubElement(part_elem, 'attr')
        a3_e.text = f"0x{entry['attr3']:02X}"

    raw_xml = ET.tostring(root, encoding='utf-8')
    dom = xml.dom.minidom.parseString(raw_xml)
    pretty_xml = dom.toprettyxml(indent='  ', encoding='utf-8').decode('utf-8')

    if output_xml_path:
        with open(output_xml_path, 'w', encoding='utf-8') as f:
            f.write(pretty_xml)
        print(f"Successfully decompiled MIBIB binary to XML: {output_xml_path}")
    else:
        print(pretty_xml)

def main():
    parser = argparse.ArgumentParser(description="Qualcomm MIBIB Partition Table Binary Decompiler (Python 3)")
    parser.add_argument("-i", "--input", required=True, help="Path to input MIBIB partition binary file (e.g. nand-system-partition.bin)")
    parser.add_argument("-o", "--output", help="Path to output XML file (prints to stdout if omitted)")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' does not exist.", file=sys.stderr)
        sys.exit(1)

    mibib_info = parse_mibib_bin(args.input)
    export_to_xml(mibib_info, args.output)

if __name__ == '__main__':
    main()
