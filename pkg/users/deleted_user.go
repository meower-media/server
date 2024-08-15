package users

var deletedFlags int64 = 0
var deletedAvatar string = ""
var deletedLegacyAvatar int8 = 0
var deletedColor string = ""
var deletedQuote string = ""

var DeletedUser User = User{
	Id:       1,
	Username: "Deleted",

	Flags:        &deletedFlags,
	Avatar:       &deletedAvatar,
	LegacyAvatar: &deletedLegacyAvatar,
	Color:        &deletedColor,
	Quote:        &deletedQuote,
}
