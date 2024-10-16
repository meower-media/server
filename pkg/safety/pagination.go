package safety

import "github.com/meower-media/server/pkg/meowid"

type SnapshotPaginationOpts struct {
	Mode   int8 // 0: before, 1: after
	ChatId meowid.MeowID
	PostId meowid.MeowID
}

func (p SnapshotPaginationOpts) BeforeId() *meowid.MeowID {
	if p.Mode == 0 {
		return &p.PostId
	} else {
		return nil
	}
}

func (p SnapshotPaginationOpts) AfterId() *meowid.MeowID {
	if p.Mode == 1 {
		return &p.PostId
	} else {
		return nil
	}
}

func (p SnapshotPaginationOpts) Skip() int64 {
	return 0
}

func (p SnapshotPaginationOpts) Limit() int64 {
	return 25
}
