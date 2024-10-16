package v0_rest

import (
	"context"
	"net/http"
	"os"

	"github.com/go-chi/chi/v5"
	"github.com/meower-media/server/pkg/db"
	"github.com/meower-media/server/pkg/networks"
	"github.com/meower-media/server/pkg/rdb"
)

func RootRouter() *chi.Mux {
	r := chi.NewRouter()

	r.Get("/", root)
	r.Get("/status", getStatus)
	r.Get("/statistics", getStatistics)
	r.Get("/favicon.ico", func(w http.ResponseWriter, r *http.Request) {}) // Favicon, my ass. We need no favicon for an API.

	return r
}

func root(w http.ResponseWriter, r *http.Request) {
	returnData(w, http.StatusOK, WelcomeResp{
		Error: false,
		Captcha: CaptchaResp{
			Enabled: os.Getenv("CAPTCHA_SECRET") != "",
			Sitekey: os.Getenv("CAPTCHA_SITEKEY"),
		},
	})
}

func getStatus(w http.ResponseWriter, r *http.Request) {
	regsDisabled, err := rdb.Client.Exists(context.TODO(), "regsdisabled").Result()
	if err != nil {
		return
	}

	repairMode, err := rdb.Client.Exists(context.TODO(), "repairmode").Result()
	if err != nil {
		return
	}

	blocked, err := networks.IsBlocked(r.RemoteAddr)
	if err != nil {
		return
	}

	returnData(w, http.StatusOK, StatusResp{
		RegistrationEnabled: regsDisabled == 1,
		RepairMode:          repairMode == 1,
		IPBlocked:           blocked,
	})
}

func getStatistics(w http.ResponseWriter, _ *http.Request) {
	userCount, err := db.Users.EstimatedDocumentCount(context.TODO())
	if err != nil {
		return
	}

	chatCount, err := db.Chats.EstimatedDocumentCount(context.TODO())
	if err != nil {
		return
	}

	postCount, err := db.Posts.EstimatedDocumentCount(context.TODO())
	if err != nil {
		return
	}

	returnData(w, http.StatusOK, StatisticsResp{
		UserCount: userCount,
		ChatCount: chatCount,
		PostCount: postCount,
	})
}
