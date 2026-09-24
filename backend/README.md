
# Backend

## Structure of the backend

The backend is structured as a layered architecture that sends requests that come to the backend most of the times to firstly a handler, then to a service and lastly, to a repository or client. The handlers are the HTTP layer that translate HTTP requests into service calls that can be understood by the backend. The services contain business and orchestration logic. The repositories do not contain any business logic and instead communicate with the database. For this they use GORM, which is an ORM library for Golang. For more information about ORM, see [ORM](ORM).
Some directories contain files that are named the same as those directories. These files contain types and structs. 

The main.go is located under /cmd/server and acts as a starting point for the backend that initialises the database, reads configuration files, injects dependencies into the components and starts the HTTP server on the configured port.

Under backend/internal/api/handler.go all registered API routes can be seen with their respective OpenAPI conform documentation

The rest of the backend code resides in the /internal directory. 

The Rest API is documented in the /docs directory using the OpenAPI standard and Swagger and it is directly used by the frontend. 

## Contributing

### Prerequisites

1. Install go as instructed here [https://go.dev/doc/install](https://go.dev/doc/install)
2. Run 
```bash
go mod tidy
```
to install all dependencies
3. You may have to write ``export PATH=$PATH:$(go env GOPATH)/bin`` into your .bashrc

### Testing the Backend

Tests in Go have the "_test" suffix. The general Go convention is to have one test file for every normal Go file that exists but this repository does not follow this convention for the files that are named after the directory they are in as these files only contain types and structs. 

To test the backend move to the backend/internal folder and run

```bash
go test ./...
```
or if you are in VSCode and have installed GOlang support, right click into the internal folder and click on "Run Tests".

### Update the API with Swagger

Changing the API in any way requires you to update the API specification and documentation. To do this run the following command in the backend folder:

 ```bash
 swag init --dir ./cmd/server,./internal/api --output ./docs
 ```
Changing the API in the backend may require you to also make changes in the frontend.

## Concepts

### Layered Architecture


### ORM

Object relational mapping is a strategy with which object oriented programming structures can be mapped into relational database structures. 
This mapping has to be done, because relational databases store object information in data tables and Go stores object information in structs which can not be automatically mapped into data tables without additional help.