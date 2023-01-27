class user:
    system = 0
    child = 1
    bot = 2
    verifiedBot = 3
    deleted = 4
    notSafeForKids = 5
    ageNotConfirmed = 6
    requireEmail = 7
    requireMFA = 8

class application:
    firstParty = 0
    hasBot = 1
    notSafeForKids = 2

class post:
    reputationHidden = 0
    commentsDisabled = 1
    edited = 3
    protected = 4
    reputationBanned = 5

class chat:
    inviteCodeDisabled = 0
    vanityInviteCode = 1
    notSafeForKids = 2

class message:
    systemAlert = 0
    edited = 1 

class infractions:
    automatic = 0
    detectAlts = 1
    poisonous = 2
    blockAppeals = 3

class admin:
    accessReports = 0
    moderateUsers = 1
    moderateIPs = 2
    moderatePosts = 3
    moderateChats = 4
    manageUsers = 5
    manageBots = 6
    manageOAuth = 7
    manageSystem = 8
