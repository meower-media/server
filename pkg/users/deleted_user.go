package users

var deletedFlags int64 = 0
var deletedPermissions int64 = 0
var deletedIconId string = ""
var deletedLegacyIcon int8 = 0
var deletedColor string = ""
var deletedQuote string = ""

var DeletedUser User = User{
	Id:       1,
	Username: "Deleted",

	Flags:       deletedFlags,
	Permissions: &deletedPermissions,

	IconId:     deletedIconId,
	LegacyIcon: deletedLegacyIcon,
	Color:      deletedColor,
	Quote:      &deletedQuote,
}
