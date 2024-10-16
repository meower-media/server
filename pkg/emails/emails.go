package emails

import (
	"bytes"
	"fmt"
	htmlTmpl "html/template"
	"log"
	"os"
	"strconv"
	txtTmpl "text/template"

	"github.com/getsentry/sentry-go"
	gomail "gopkg.in/mail.v2"
)

var emailSubjects = map[string]string{
	"verify":         "Verify your email address",
	"recover":        "Reset your password",
	"security_alert": "Security alert",
	"locked":         "Your account has been locked",
}

type EmailTmplVars struct {
	PlatformName     string
	PlatformLogo     string
	PlatformBrand    string
	PlatformFrontend string
	PlatformSupport  string

	FromName    string
	FromAddress string

	Subject   string
	ToName    string
	ToAddress string
	Token     string
}

func SendEmail(tmplName, toName, toAddress, token string) {
	go func() {
		// Create message vars
		vars := EmailTmplVars{
			PlatformName:     os.Getenv("EMAIL_PLATFORM_NAME"),
			PlatformLogo:     os.Getenv("EMAIL_PLATFORM_LOGO"),
			PlatformBrand:    os.Getenv("EMAIL_PLATFORM_BRAND"),
			PlatformFrontend: os.Getenv("EMAIL_PLATFORM_FRONTEND"),
			PlatformSupport:  os.Getenv("EMAIL_PLATFORM_SUPPORT"),

			FromName:    os.Getenv("EMAIL_FROM_NAME"),
			FromAddress: os.Getenv("EMAIL_FROM_ADDRESS"),

			Subject:   emailSubjects[tmplName],
			ToName:    toName,
			ToAddress: toAddress,
			Token:     token,
		}

		// Create message
		m := gomail.NewMessage()
		m.SetHeader("From", fmt.Sprintf("%s <%s>", vars.FromName, vars.FromAddress))
		m.SetHeader("To", fmt.Sprintf("%s <%s>", vars.ToName, vars.ToAddress))
		m.SetHeader("Subject", vars.Subject)

		// Render templates
		var txtTmplBuf, htmlTmplBuf bytes.Buffer
		_, err := txtTmpl.ParseFiles("pkg/emails/templates/base.txt", fmt.Sprintf("pkg/emails/templates/%s.txt", tmplName))
		if err != nil {
			log.Fatalln(err)
			sentry.CaptureException(err)
			return
		}
		//tt.Execute(&txtTmplBuf, &vars)
		ht, err := htmlTmpl.ParseFiles("pkg/emails/templates/base.html", fmt.Sprintf("pkg/emails/templates/%s.html", tmplName))
		if err != nil {
			log.Fatalln(err)
			sentry.CaptureException(err)
			return
		}
		ht.Execute(&htmlTmplBuf, &vars)

		// Set message body
		m.SetBody("text/plain", txtTmplBuf.String())
		m.AddAlternative("text/html", htmlTmplBuf.String())

		// Send message
		host := os.Getenv("EMAIL_SMTP_HOST")
		port, _ := strconv.Atoi(os.Getenv("EMAIL_SMTP_PORT"))
		if err := gomail.NewDialer(
			host,
			port,
			os.Getenv("EMAIL_SMTP_USERNAME"),
			os.Getenv("EMAIL_SMTP_PASSWORD"),
		).DialAndSend(m); err != nil {
			log.Fatalln(err)
			sentry.CaptureException(err)
		}
	}()
}
