package db

import (
	"context"
	"os"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

var Client *mongo.Client
var Database *mongo.Database

var (
	Config          *mongo.Collection
	Accounts        *mongo.Collection
	Users           *mongo.Collection
	UserSettings    *mongo.Collection
	AccSessions     *mongo.Collection
	Netblock        *mongo.Collection
	Relationships   *mongo.Collection
	Chats           *mongo.Collection
	ChatMembers     *mongo.Collection
	ChatEmotes      *mongo.Collection
	Posts           *mongo.Collection
	PostReactions   *mongo.Collection
	Reports         *mongo.Collection
	ReportSnapshots *mongo.Collection
	Strikes         *mongo.Collection
	Files           *mongo.Collection
)

func Init(uri string, db string) error {
	var err error

	// Connect to MongoDB
	serverAPI := options.ServerAPI(options.ServerAPIVersion1)
	opts := options.Client().ApplyURI(uri).SetServerAPIOptions(serverAPI)
	Client, err = mongo.Connect(context.TODO(), opts)
	if err != nil {
		return err
	}

	// Ping MongoDB
	var result bson.M
	if err := Client.Database("admin").RunCommand(context.TODO(), bson.D{{Key: "ping", Value: 1}}).Decode(&result); err != nil {
		return err
	}

	// Set database
	Database = Client.Database(os.Getenv("MONGO_DB"))

	// Set collections
	Config = Database.Collection("config")
	Accounts = Database.Collection("accounts")
	Users = Database.Collection("users")
	UserSettings = Database.Collection("user_settings")
	AccSessions = Database.Collection("acc_sessions")
	Netblock = Database.Collection("netblock")
	Relationships = Database.Collection("relationships")
	Chats = Database.Collection("chats")
	ChatMembers = Database.Collection("chat_members")
	ChatEmotes = Database.Collection("chat_emotes")
	Posts = Database.Collection("posts")
	PostReactions = Database.Collection("post_reactions")
	Reports = Database.Collection("reports")
	ReportSnapshots = Database.Collection("report_snapshots")
	Strikes = Database.Collection("strikes")
	Files = Database.Collection("files")

	return nil
}
