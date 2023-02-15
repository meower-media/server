# This is just a file that displays the current version number of the server.

# VERSION - Change when a release is made - Currently using Vanilla semantic versioning (it's awful)
VERSION = "0.6.0-cl4-dev"

# BUILD_DATE - Provide an epoch time stamp of the server's most recent change before commits.
BUILD_DATE = 1675960612


def display_version():
    # TODO: Make this a log event
    print(f"Meower Server - Version {VERSION} - Build {BUILD_DATE}")
