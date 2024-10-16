package v0_rest

import (
	"net/http"
	"strconv"

	"github.com/meower-media/server/pkg/meowid"
)

const defaultPaginationLimit = 25

type PaginationOpts struct {
	Request *http.Request
}

func (p PaginationOpts) BeforeId() *meowid.MeowID {
	beforeId, err := strconv.ParseInt(p.Request.URL.Query().Get("before"), 10, 64)
	if err == nil {
		return &beforeId
	}

	return nil
}

func (p PaginationOpts) AfterId() *meowid.MeowID {
	afterId, err := strconv.ParseInt(p.Request.URL.Query().Get("after"), 10, 64)
	if err == nil {
		return &afterId
	}

	return nil
}

func (p PaginationOpts) Skip() int64 {
	page, err := strconv.ParseInt(p.Request.URL.Query().Get("page"), 10, 64)
	if err == nil {
		skip := (page - 1) * 25
		return skip
	}

	return 0
}

func (p PaginationOpts) Limit() int64 {
	limit, err := strconv.ParseInt(p.Request.URL.Query().Get("limit"), 10, 64)
	if err == nil {
		// limit the limit to 100
		if limit > 100 {
			return 100
		}

		return limit
	}

	return defaultPaginationLimit
}

func (p PaginationOpts) Page() int64 {
	page, err := strconv.ParseInt(p.Request.URL.Query().Get("page"), 10, 64)
	if err == nil {
		return page
	}

	return 1
}
