import os
from uuid import uuid4
import argparse


# Make the table
table = {
    'A': ' _________\n(____  _  )\n ___| |_| |\n(_________)\n',
    'B': ' _________\n(  _   _  )\n| |_| |_| |\n(____/\\___)\n',
    'C': ' _________\n(  _____  )\n| |     | |\n(_)     (_)\n',
    'D': ' _________\n(  _____  )\n \\ \\___/ / \n  (_____)\n',
    'E': ' _________\n(  _   _  )\n| | | | | |\n(_) (_) (_)\n',
    'F': ' _________\n(___   _  )\n    | | | |\n    (_) (_)\n',
    'G': ' _________\n(  _____  )\n| |_    | |\n(___)   (_)\n',
    'H': ' _________\n(___   ___)\n ___| |___ \n(_________)\n',
    'I': ' ______ __\n(_______(_)\n',
    'J': ' __       \n(  _)      \n| |_______ \n(_________)\n',
    'K': ' _________\n(___    __)\n __/ __ \\_ \n(___/  \\__)\n',
    'L': ' _________\n(  _______)\n| |        \n(_)\n',
    'M': ' _________\n(______   )\n _____(   )\n(_________)\n',
    'N': ' _________\n(______  _)\n _____/ /_ \n(_________)\n',
    'O': ' _________\n(  _____  )\n| |_____| |\n(_________)\n',
    'P': ' _________\n(___   _  )\n    | |_| |\n    (_____)\n',
    'Q': ' _________\n(  _____  )\n| |_____| |\n(_)_______)\n',
    'R': ' _________\n(___   _  )\n _/   |_| |\n(__/(_____)\n',
    'S': '     _____\n( ) (  _  )\n| |_| | | |\n(_____) (_)\n',
    'T': '         _\n _______| |\n(_______  |\n        |_|\n',
    'U': ' _________\n(  _______)\n| |_______ \n(_________)\n',
    'V': '  ________\n / _______)\n| (_______ \n \\________)\n',
    'W': ' _________\n(  _______)\n(  __)____ \n(_________)\n',
    'X': ' ____  ___\n(__  \\/  _)\n __)    (_ \n(____/\\___)\n',
    'Y': '     _____\n ___/  ___)\n(___  (___ \n    \\_____)\n',
    'Z': ' _____   _\n(  _  ) ( )\n| | | |_| |\n(_) (_____)\n',
    ' ': '\n\n',
}
trans = str.maketrans(table)


# Get the args
def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "text",
        action="extend",
        nargs="+",
    )
    parser.add_argument(
        "--big",
        action="store_true",
    )
    return parser


# Let's go gamers
if __name__ == "__main__":
    args = make_parser().parse_args()
    text = " ".join(args.text)
    if args.big:
        letters = [x.translate(trans) if x in table else f"{x}\n" for x in text.upper()]
        text = "".join(letters)
    filename = f"{uuid4()}.txt"
    with open(filename, "w", encoding="utf8") as a:
        a.write(text)
    os.system(f"notepad /p {filename}")
    os.system(f"del {filename}")
