# This is just a file that displays the current version number of the server.

# version - Change when a release is made - Currently using Vanilla semantic versioning (it's awful)
version = "0.6.0-cl4-dev"

# buildDate - Provide an epoch time stamp of the server's most recent change before commits.
buildDate = 1675960612


def displayMeowerVersion():
    # TODO: Make this a log event...
    print(f"\nMeower Server - Version {version} - Build {buildDate}\n")