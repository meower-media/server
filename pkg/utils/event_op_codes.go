package utils

// temporary implementation symbols
// '// *' means it's implemented in the events package, but isn't going to be used in the events API
// '// //' means it's implemented in the events package and events API
// no comment means it's yet to be implemented

const (
	EvOpCreateUser uint8 = 0 // *
	EvOpUpdateUser uint8 = 1 // //
	EvOpDeleteUser uint8 = 2 // *

	EvOpUpdateUserSettings uint8 = 3

	EvOpRevokeSession uint8 = 4

	EvOpUpdateRelationship uint8 = 5 // //

	EvOpCreateChat uint8 = 6
	EvOpUpdateChat uint8 = 7
	EvOpDeleteChat uint8 = 8

	EvOpCreateChatMember uint8 = 9
	EvOpUpdateChatMember uint8 = 10
	EvOpDeleteChatMember uint8 = 11

	EvOpCreateChatEmote uint8 = 12
	EvOpUpdateChatEmote uint8 = 13
	EvOpDeleteChatEmote uint8 = 14

	EvOpTyping uint8 = 15 // //

	EvOpCreatePost      uint8 = 16 // //
	EvOpUpdatePost      uint8 = 17 // //
	EvOpDeletePost      uint8 = 18 // //
	EvOpBulkDeletePosts uint8 = 19 // //

	EvOpPostReactionAdd    uint8 = 20 // //
	EvOpPostReactionRemove uint8 = 21 // //
)
