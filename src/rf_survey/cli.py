import argparse

from rf_survey.config import AppSettings


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


def positive_float(value: str) -> float:
    """Ensure the value is a positive float for argparse."""
    try:
        num = float(value)
        if num <= 0:
            raise argparse.ArgumentTypeError(f"{value} must be a positive number.")
        return num
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not a valid number.")


def update_settings_from_args(settings: AppSettings) -> AppSettings:
    """
    Parses CLI arguments and updates the provided settings object.
    CLI arguments take precedence over defaults, but not over environment variables.
    """
    parser = argparse.ArgumentParser(
        description="UHD RF Sweeper for IQ data collection.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "-f1",
        "--frequency_start",
        type=positive_int_float,
        default=settings.FREQUENCY_START,
        help="Start Center Frequency in Hz (e.g., 915e6). Env: RF_FREQUENCY_START",
    )
    parser.add_argument(
        "-f2",
        "--frequency_end",
        type=positive_int_float,
        default=settings.FREQUENCY_END,
        help="End Center Frequency in Hz (e.g., 920e6). Env: RF_FREQUENCY_END",
    )
    parser.add_argument(
        "-b",
        "--bandwidth",
        type=positive_int_float,
        default=settings.BANDWIDTH,
        help="Bandwidth in Hz (e.g., 2e6). Env: RF_BANDWIDTH",
    )
    parser.add_argument(
        "-d",
        "--duration_sec",
        type=positive_float,
        default=settings.DURATION_SEC,
        help="Capture duration in seconds. Env: RF_DURATION_SEC",
    )
    parser.add_argument(
        "-g",
        "--gain",
        type=gain_check,
        default=settings.GAIN,
        help="Receive gain in dB (0-76). Env: RF_GAIN",
    )
    parser.add_argument(
        "-r",
        "--records",
        type=int,
        default=settings.RECORDS,
        help="# of files generated per frequency. Env: RF_RECORDS",
    )
    parser.add_argument(
        "-o",
        "--organization",
        type=str,
        default=settings.ORGANIZATION,
        help="Organization Identifier. Env: RF_ORGANIZATION",
    )
    parser.add_argument(
        "-gcs",
        "--coordinates",
        type=str,
        default=settings.COORDINATES,
        help="Coordinates in 40.0149N105.2705W format. Env: RF_COORDINATES",
    )
    parser.add_argument(
        "-c",
        "--cycles",
        type=int,
        default=settings.CYCLES,
        help="# of times all frequencies are swept. Set to 0 for continuous. Env: RF_CYCLES",
    )
    parser.add_argument(
        "-t",
        "--timer",
        type=positive_float,
        default=settings.TIMER,
        help="Time interval in seconds between captures. Env: RF_TIMER",
    )
    parser.add_argument(
        "-j",
        "--jitter",
        type=float,
        default=settings.JITTER,
        help="Max random jitter in seconds to add to the timer. Env: RF_JITTER",
    )

    parser.set_defaults(
        frequency_start=settings.FREQUENCY_START,
        frequency_end=settings.FREQUENCY_END,
        bandwidth=settings.BANDWIDTH,
        duration_sec=settings.DURATION_SEC,
        gain=settings.GAIN,
        records=settings.RECORDS,
        organization=settings.ORGANIZATION,
        coordinates=settings.COORDINATES,
        cycles=settings.CYCLES,
        timer=settings.TIMER,
        jitter=settings.JITTER,
    )

    args = parser.parse_args()
    cli_args_dict = vars(args)
    cli_args_uppercase = {key.upper(): value for key, value in cli_args_dict.items()}

    updated_settings = AppSettings(**cli_args_uppercase)

    return updated_settings


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
        "-d",
        "--duration_sec",
        type=positive_int_float,
        required=True,
        help="Capture duration in seconds.",
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
        "-j",
        "--jitter",
        nargs="?",
        const=0.1,
        default=0.0,
        type=float,
        help=(
            "Enable jitter. If the flag is present without a value, a default max "
            "jitter of 0.1s is used. Optionally, provide a value for a different "
            "max jitter (e.g., -j 0.5)."
        ),
    )

    args = parser.parse_args()

    if not args.frequency_end:
        args.frequency_end = args.frequency_start

    if args.frequency_end < args.frequency_start:
        parser.error("frequency_end must be greater than or equal to frequency_start.")

    return args
