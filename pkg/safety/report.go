package safety

import (
	"context"
	"strconv"

	"github.com/meower-media/server/pkg/db"
	"github.com/meower-media/server/pkg/meowid"
	"github.com/meower-media/server/pkg/structs"
)

type Report struct {
	Id           meowid.MeowID `bson:"_id"`
	Type         string        `bson:"type"` // "user" / "chat" / "post"
	ContentId    meowid.MeowID `bson:"content"`
	SnapshotHash string        `bson:"snapshot"`
	ReporterId   meowid.MeowID `bson:"reporter"`
	Reason       string        `bson:"reason"`
	Comment      string        `bson:"comment"`
	Status       string        `bson:"status"` // "pending" / "no_action_taken" / "action_taken"
}

func CreateReport(reportType string, contentId meowid.MeowID, reporterId meowid.MeowID, reason string, comment string) (Report, error) {
	var report Report
	var snapshot Snapshot
	var err error

	// Create snapshot
	if reportType == "user" {
		snapshot, err = CreateUserSnapshot(contentId)
	}
	if reportType == "post" {
		snapshot, err = CreatePostSnapshot(contentId)
	}
	if err != nil {
		return report, err
	}

	// Create report
	report = Report{
		Id:           meowid.GenId(),
		Type:         reportType,
		ContentId:    contentId,
		SnapshotHash: snapshot.Hash,
		ReporterId:   reporterId,
		Reason:       reason,
		Comment:      comment,
		Status:       "pending",
	}
	if _, err := db.Reports.InsertOne(context.TODO(), report); err != nil {
		return report, err
	}

	return report, nil
}

// this is for the reporter, not admin
func (r *Report) V0() structs.V0Report {
	return structs.V0Report{
		Id:        strconv.FormatInt(r.Id, 10),
		Type:      r.Type,
		ContentId: strconv.FormatInt(r.ContentId, 10),
		Content:   nil,
		Reason:    r.Reason,
		Comment:   r.Comment,
		Time:      meowid.Extract(r.Id).Timestamp / 1000,
		Status:    r.Status,
	}
}
