package posts

type Attachment struct {
	Id       string `msgpack:"id"`
	Mime     string `msgpack:"mime"`
	Filename string `msgpack:"filename"`
	Size     int    `msgpack:"size"`
	Width    int    `msgpack:"width"`
	Height   int    `msgpack:"height"`
}
