package events

// temporary implementation symbols
// '// *' means it's implemented in the events package, but isn't going to be used in the events API
// '// //' means it's implemented in the events package and events API
// no comment means it's yet to be implemented

const (
	OpCreateUser uint8 = 0 // *
	OpUpdateUser uint8 = 1 // //
	OpDeleteUser uint8 = 2 // *

	OpUpdateUserSettings uint8 = 3

	OpRevokeSession uint8 = 4

	OpUpdateRelationship uint8 = 5 // //

	OpCreateChat uint8 = 6
	OpUpdateChat uint8 = 7
	OpDeleteChat uint8 = 8

	OpCreateChatMember uint8 = 9
	OpUpdateChatMember uint8 = 10
	OpDeleteChatMember uint8 = 11

	OpCreateChatEmote uint8 = 12
	OpUpdateChatEmote uint8 = 13
	OpDeleteChatEmote uint8 = 14

	OpTyping uint8 = 15 // //

	OpCreatePost      uint8 = 16 // //
	OpUpdatePost      uint8 = 17 // //
	OpDeletePost      uint8 = 18 // //
	OpBulkDeletePosts uint8 = 19 // //

	OpPostReactionAdd    uint8 = 20 // //
	OpPostReactionRemove uint8 = 21 // //
)
