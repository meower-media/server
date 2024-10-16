package networks

import (
	"context"
	"net"

	"github.com/meower-media/server/pkg/db"
	"github.com/meower-media/server/pkg/meowid"
	"github.com/meower-media/server/pkg/rdb"
	"github.com/vmihailenco/msgpack/v5"
	"github.com/yl2chen/cidranger"
)

var (
	OpCreateBlock byte = 0x1
	OpDeleteBlock byte = 0x2
)

var ranger = cidranger.NewPCTrieRanger()

type BlockEntry struct {
	Id        meowid.MeowID `bson:"_id"`
	Address   string        `bson:"address"`
	ExpiresAt int64         `bson:"expires_at"`
}

func (b BlockEntry) Network() net.IPNet {
	_, net, _ := net.ParseCIDR(b.Address)
	return *net
}

func CreateBlock(address string, expiresAt int64) (BlockEntry, error) {
	entry := BlockEntry{
		Id:        meowid.GenId(),
		Address:   address,
		ExpiresAt: expiresAt,
	}

	if err := ranger.Insert(entry); err != nil {
		return entry, err
	}

	// Store in database
	if _, err := db.Netblock.InsertOne(context.TODO(), entry); err != nil {
		return entry, err
	}

	// Tell other instances about the block
	marshaledEntry, err := msgpack.Marshal(entry)
	if err != nil {
		return entry, err
	}
	marshaledEntry = append([]byte{OpCreateBlock}, marshaledEntry...)
	err = rdb.Client.Publish(context.TODO(), "firewall", marshaledEntry).Err()
	if err != nil {
		return entry, err
	}

	return entry, nil
}

func IsBlocked(address string) (bool, error) {
	return ranger.Contains(net.ParseIP(address))
}
