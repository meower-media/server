package structs

type V0UserSettings struct {
	Theme            *string `json:"theme,omitempty"`
	Mode             *bool   `json:"mode,omitempty"`
	Layout           *string `json:"layout,omitempty"`
	Sfx              *bool   `json:"sfx,omitempty"`
	Bgm              *bool   `json:"bgm,omitempty"`
	BgmSong          *int8   `json:"bgm_song,omitempty"`
	Debug            *bool   `json:"debug,omitempty"`
	HideBlockedUsers *bool   `json:"hide_blocked_users,omitempty"`
}

var (
	v0DefaultTheme            string = "orange"
	v0DefaultMode             bool   = true
	v0DefaultLayout           string = "new"
	v0DefaultSfx              bool   = true
	v0DefaultBgm              bool   = false
	v0DefaultBgmSong          int8   = 1
	v0DefaultDebug            bool   = false
	v0DefaultHideBlockedUsers bool   = false
)

var V0DefaultUserSettings = V0UserSettings{
	Theme:            &v0DefaultTheme,
	Mode:             &v0DefaultMode,
	Layout:           &v0DefaultLayout,
	Sfx:              &v0DefaultSfx,
	Bgm:              &v0DefaultBgm,
	BgmSong:          &v0DefaultBgmSong,
	Debug:            &v0DefaultDebug,
	HideBlockedUsers: &v0DefaultHideBlockedUsers,
}
