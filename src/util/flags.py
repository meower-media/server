class user:
    system = 0
    child = 1
    bot = 2
    verifiedBot = 3
    notSafeForKids = 4
    deleted = 5
    terminated = 6

class account:
    ageNotConfirmed = 0
    requireEmail = 1
    requireMFA = 2
    requireParentLink = 3

class guardian:
    blocked = 0
    forceFilter = 1
    forcePrivate = 2

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

class suspension:
    createPosts = 0
    createComments = 1
    likePosts = 2
    meowPosts = 3
    sendMessages = 4
    likeMessages = 5
    editProfile = 6
    uploadFiles = 7
    followUsers = 8
    createReports = 9

class chat:
    inviteCodeDisabled = 0
    vanityInviteCode = 1
    notSafeForKids = 2

class post:
    reputationHidden = 0
    commentsDisabled = 1
    edited = 3
    protected = 4
    reputationBanned = 5      

class message:
    systemAlert = 0
    edited = 1 
