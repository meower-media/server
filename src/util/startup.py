# This is just a file that displays the current version number of the server.

# VERSION - Change when a release is made - Currently using Vanilla semantic versioning (it's awful)
VERSION = "0.6.0-cl4-dev"

# BUILD_DATE - Provide an epoch time stamp of the server's most recent change before commits.
BUILD_DATE = 1680318412


def display_version():
    # TODO: Make this a log event
    print(f"Meower Server v{VERSION} ({BUILD_DATE})")
