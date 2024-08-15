package posts

type ReactionIndex struct {
	Emoji string `msgpack:"emoji"`
	Count int    `msgpack:"count"`
}
