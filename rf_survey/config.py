import argparse


def gain_check(g):
    """Validate that gain is within the 0-76 range."""
    num = int(g)
    if not 0 <= num <= 76:
        raise argparse.ArgumentTypeError("Valid gain values range from 0 to 76")
    return num


def positive_int_float(value):
    """Allow scientific notation and ensure the result is a positive integer."""
    try:
        num = int(float(value))
        if num <= 0:
            raise argparse.ArgumentTypeError(f"{value} must be a positive number.")
        return num
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value} is not a valid number.")


def parse_args():
    parser = argparse.ArgumentParser(
        description="UHD RF Sweeper for IQ data collection."
    )

    required = parser.add_argument_group("required named arguments")

    required.add_argument(
        "-f1",
        "--frequency_start",
        type=positive_int_float,
        required=True,
        help="Start Center Frequency in Hz (e.g., 915e6)",
    )
    parser.add_argument(
        "-f2",
        "--frequency_end",
        type=positive_int_float,
        help="End Center Frequency in Hz (e.g., 920e6)",
    )
    required.add_argument(
        "-b",
        "--bandwidth",
        type=positive_int_float,
        required=True,
        help="Bandwidth in Hz (e.g., 2e6)",
    )
    required.add_argument(
        "-s",
        "--samples",
        type=positive_int_float,
        required=True,
        help="Total number of samples",
    )
    required.add_argument(
        "-g", "--gain", type=gain_check, required=True, help="Receive gain in dB (0-76)"
    )
    required.add_argument(
        "-r",
        "--records",
        type=int,
        required=True,
        help="# of files generated per frequency",
    )
    required.add_argument(
        "-o", "--organization", type=str, required=True, help="Location Identifier"
    )
    required.add_argument(
        "-gcs",
        "--coordinates",
        type=str,
        required=True,
        help="Coordinates in 40.0149N105.2705W format",
    )
    parser.add_argument(
        "-c",
        "--cycles",
        type=int,
        default=1,
        help="# of times all frequencies are swept. Set to 0 for continuous mode.",
    )
    required.add_argument(
        "-t",
        "--timer",
        type=float,
        required=True,
        help="Time interval in seconds - min = BW/1e6*0.2",
    )
    parser.add_argument(
        "-m", "--maxtimer", type=int, help="Max random time interval in seconds"
    )
    parser.add_argument(
        "-d",
        "--delay",
        type=float,
        default=0,
        help="Execute the script [x] seconds in the future",
    )
    parser.add_argument(
        "-rs",
        "--seed",
        type=int,
        help="only used when activating multiple devices through the GUI",
    )

    args = parser.parse_args()

    if not args.frequency_end:
        args.frequency_end = args.frequency_start

    if args.frequency_end < args.frequency_start:
        parser.error("frequency_end must be greater than or equal to frequency_start.")

    if args.timer == 0:
        if args.maxtimer is None:
            parser.error("-m/--maxtimer is required when -t/--timer is set to 0.")

        min_maxtimer = args.bandwidth / 1e6 * 0.2
        if args.maxtimer < min_maxtimer:
            parser.error(f"maxtimer must be at least {min_maxtimer} (BW/1e6*0.2).")

    return args
