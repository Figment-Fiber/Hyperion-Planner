"""Compare the live adapter with both independently captured CLI tables."""

from pathlib import Path

from gnpy_reference import run_reference


def read_cli_table(path):
    raw = path.read_bytes()
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8"
    output = raw.decode(encoding)
    _, table = output.split("Channel frequency (THz)", 1)
    return [
        (int(fields[0]), float(fields[1]), float(fields[3]), float(fields[5]))
        for line in table.splitlines()[1:]
        if len(fields := line.split()) == 6 and fields[0].isdigit()
    ]


def main():
    evidence = Path(__file__).parent / "evidence" / "gnpy-3.0.1"
    for case, override, length in (("bundled", None, 80), ("override", 85.25, 85.25)):
        expected = read_cli_table(evidence / f"{case}.stdout.txt")
        result = run_reference(override)
        observed = [
            (row["channel"], row["frequency_thz"], row["osnr_ase_db"], row["gsnr_db"])
            for row in result["channels"]
        ]
        if len(expected) != 76 or observed != expected or result["span_length_km"] != length:
            raise AssertionError(f"{case}: adapter and CLI results differ")
        print(f"{case}: all {len(observed)} channels match at {length} km")


if __name__ == "__main__":
    main()
