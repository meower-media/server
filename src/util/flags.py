class users:
    system = 0
    bot = 1
    verifiedBot = 2
    deleted = 3
    ageNotConfirmed = 4
    requireEmail = 5
    requireMFA = 6

class applications:
    firstParty = 0
    hasBot = 1

class posts:
    bridged = 0
    reputationHidden = 1
    commentsDisabled = 2
    edited = 3
    protected = 4
    reputationBanned = 5

class comments:
    bridged = 0
    edited = 1

class chats:
    inviteCodeDisabled = 0
    vanityInviteCode = 1

class messages:
    systemAlert = 0
    bridged = 1
    edited = 2

class infractions:
    automatic = 0
    detectAlts = 1
    poisonous = 2
    blockAppeals = 3

class adminScopes:
    accessReports = 0
    moderateUsers = 1
    moderateIPs = 2
    moderatePosts = 3
    moderateChats = 4
    manageUsers = 5
    manageBots = 6
    manageOAuth = 7
    manageSystem = 8
