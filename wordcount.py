import argparse
from collections import Counter
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    args = parser.parse_args()

    text = Path(args.file).read_text(encoding="utf-8")
    words = text.split()
    for word, count in Counter(words).most_common(10):
        print(f"{word}: {count}")

if __name__ == "__main__":
    main()