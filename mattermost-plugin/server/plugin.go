package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"strings"

	"github.com/mattermost/mattermost-server/v6/model"
	"github.com/mattermost/mattermost-server/v6/plugin"
)

type configuration struct {
	BackendURL string `json:"BackendURL"`
}

type Plugin struct {
	plugin.MattermostPlugin

	configurationLock sync.RWMutex
	configuration     *configuration
}

func (p *Plugin) OnConfigurationChange() error {
	var configuration = new(configuration)
	if err := p.API.LoadPluginConfiguration(configuration); err != nil {
		return err
	}
	p.configurationLock.Lock()
	p.configuration = configuration
	p.configurationLock.Unlock()
	return nil
}

func (p *Plugin) OnActivate() error {
	// Register the /taco slash command
	err := p.API.RegisterCommand(&model.Command{
		Trigger:          "taco",
		Description:      "Interact with Tito the Taco Shop Bot",
		DisplayName:      "Tito Taco Shop",
		AutoComplete:     true,
		AutoCompleteDesc: "Available commands: (no args) or `leaderboard`",
		AutoCompleteHint: "[leaderboard]",
	})
	if err != nil {
		return fmt.Errorf("failed to register command: %w", err)
	}

	// Ensure the bot user exists
	botId, err := p.Helpers.EnsureBot(&model.Bot{
		Username:    "tito",
		DisplayName: "Tito",
		Description: "Taco Shop Bot",
	})
	if err != nil {
		return fmt.Errorf("failed to ensure tito bot: %w", err)
	}

	// Create a personal access token for the bot so the Django backend can use it for the WebSocket
	token, tokenErr := p.API.CreateUserAccessToken(botId, "Generated for Django WebSocket")
	if tokenErr != nil {
		p.API.LogWarn("Failed to create user access token, token may already exist", "error", tokenErr.Error())
	} else if token != nil {
		// Send registration payload to Django backend
		p.configurationLock.RLock()
		backendURL := p.configuration.BackendURL
		p.configurationLock.RUnlock()
		
		if backendURL != "" {
			config := p.API.GetConfig()
			siteURL := ""
			if config.ServiceSettings.SiteURL != nil {
				siteURL = *config.ServiceSettings.SiteURL
			}

			payload := map[string]string{
				"team_id": "mattermost", 
				"bot_token": token.Token,
				"bot_user_id": botId,
				"site_url": siteURL,
			}
			jsonData, _ := json.Marshal(payload)
			
			resp, httpErr := http.Post(
				strings.TrimSuffix(backendURL, "/")+"/integration/mattermost/register/", 
				"application/json", 
				bytes.NewBuffer(jsonData),
			)
			if httpErr == nil && resp != nil {
				defer resp.Body.Close()
			}
		}
	}

	return nil
}

func (p *Plugin) ExecuteCommand(c *plugin.Context, args *model.CommandArgs) (*model.CommandResponse, *model.AppError) {
	if strings.HasPrefix(args.Command, "/taco") {
		p.configurationLock.RLock()
		backendURL := p.configuration.BackendURL
		p.configurationLock.RUnlock()

		if backendURL == "" {
			return &model.CommandResponse{
				ResponseType: model.CommandResponseTypeEphemeral,
				Text:         "Tito Backend URL is not configured. Please set it in the plugin settings.",
			}, nil
		}

		// Forward the text payload to Django
		token := "" // TODO: fetching the bot token from KV store here for proper auth verification when this goes public. Skipped for brevity in this example.
		payload := fmt.Sprintf("team_id=mattermost&token=%s&command=/taco&text=%s&user_id=%s&channel_id=%s", 
			token, 
			strings.TrimSpace(strings.TrimPrefix(args.Command, "/taco")), 
			args.UserId, 
			args.ChannelId,
		)

		resp, err := http.Post(
			strings.TrimSuffix(backendURL, "/")+"/integration/mattermost/slash/",
			"application/x-www-form-urlencoded",
			strings.NewReader(payload),
		)

		if err != nil {
			return &model.CommandResponse{
				ResponseType: model.CommandResponseTypeEphemeral,
				Text:         "Error contacting Tito backend: " + err.Error(),
			}, nil
		}
		defer resp.Body.Close()

		var jsonResp struct {
			Text         string `json:"text"`
			ResponseType string `json:"response_type"`
		}
		json.NewDecoder(resp.Body).Decode(&jsonResp)

		return &model.CommandResponse{
			ResponseType: model.CommandResponseTypeEphemeral, // Force ephemeral for stats
			Text:         jsonResp.Text,
		}, nil
	}

	return nil, nil
}
