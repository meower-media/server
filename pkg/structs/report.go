package structs

type V0Report struct {
	Id        string      `json:"_id"`
	Type      string      `json:"type"`
	ContentId string      `json:"content_id"`
	Content   interface{} `json:"content"`
	Reason    string      `json:"reason"`
	Comment   string      `json:"comment"`
	Time      int64       `json:"time"`
	Status    string      `json:"status"`
}
