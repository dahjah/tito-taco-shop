PLUGIN_ID ?= com.internal.titotacos

GO ?= go

all: dist

dist:
	mkdir -p server/dist
	GOOS=linux GOARCH=amd64 $(GO) build -o server/dist/plugin-linux-amd64 ./server
	GOOS=darwin GOARCH=amd64 $(GO) build -o server/dist/plugin-darwin-amd64 ./server
	GOOS=windows GOARCH=amd64 $(GO) build -o server/dist/plugin-windows-amd64.exe ./server
	mkdir -p dist/$(PLUGIN_ID)
	cp plugin.json dist/$(PLUGIN_ID)/
	cp -r server/dist dist/$(PLUGIN_ID)/server
	cd dist && tar -czvf $(PLUGIN_ID).tar.gz $(PLUGIN_ID)

clean:
	rm -rf server/dist
	rm -rf dist
