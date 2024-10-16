package meowid

import (
	"math"
	"strconv"
	"sync"
	"time"
)

// MeowID Format:
// Timestamp (42-bits)
// Node ID (11-bits)
// Increment (11-bits)

type MeowID = int64

const MeowerEpoch int64 = 1577836800000 // 2020-01-01 12am GMT

const (
	TimestampBits = 41
	TimestampMask = (1 << TimestampBits) - 1

	NodeIdBits = 11
	NodeIdMask = (1 << NodeIdBits) - 1

	IncrementBits = 11
)

var NodeId int
var MaxIncrement = math.Pow(2, IncrementBits) - 1

var idIncrementLock = sync.Mutex{}
var idIncrementTs int64 = 0
var idIncrement int64 = 0

func Init(nodeId string) error {
	var err error
	NodeId, err = strconv.Atoi(nodeId)
	return err
}

func GenId() int64 {
	// Get timestamp
	ts := time.Now().UnixMilli()

	// Get increment
	idIncrementLock.Lock()
	defer idIncrementLock.Unlock()
	if idIncrementTs != ts {
		idIncrementTs = ts
		idIncrement = 0
	} else if idIncrement >= int64(math.Pow(2, IncrementBits))-1 {
		for time.Now().UnixMilli() == ts {
			continue
		}
		return GenId()
	} else {
		idIncrement += 1
	}

	// Construct ID
	id := (ts - MeowerEpoch) << (NodeIdBits + IncrementBits)
	id |= int64(NodeId) << IncrementBits
	id |= idIncrement

	return id
}

// WARNING: This may result in conflicts because it generates the 1st possible
// ID for the given timestamp.
func GenIdForTs(ts int64) int64 {
	// Construct ID
	id := (ts - MeowerEpoch) << (NodeIdBits + IncrementBits)
	id |= 0 << IncrementBits
	id |= 0

	return id
}

func Extract(id int64) struct {
	Timestamp int64
	NodeId    int64
	Increment int64
} {
	return struct {
		Timestamp int64
		NodeId    int64
		Increment int64
	}{
		Timestamp: ((id >> (64 - TimestampBits - 1)) & TimestampMask) + MeowerEpoch,
		NodeId:    (id >> (64 - TimestampBits - NodeIdBits - 1)) & NodeIdMask,
		Increment: id & NodeIdMask,
	}
}
