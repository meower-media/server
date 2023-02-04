from datetime import datetime

class PrintColors:
    """
    Nice colors used for when printing logs to the console.
    """

    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    END = "\033[0m"

def success(event: str):
    print("{0}[{1}]".format(PrintColors.GREEN, datetime.now().strftime("%m/%d/%Y %H:%M.%S")), "[SUCCESS]", event, PrintColors.END)

def info(event: str):
    print("[{0}]".format(datetime.now().strftime("%m/%d/%Y %H:%M.%S")), "[INFO]", event, "")

def warn(event: str):
    print("{0}[{1}]".format(PrintColors.YELLOW, datetime.now().strftime("%m/%d/%Y %H:%M.%S")), "[WARNING]", event, PrintColors.END)

def error(event: str):
    print("{0}[{1}]".format(PrintColors.RED, datetime.now().strftime("%m/%d/%Y %H:%M.%S")), "[ERROR]", event, PrintColors.END)
