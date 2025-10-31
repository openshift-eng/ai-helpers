package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"net/url"
	"os"
	"strings"

	"github.com/vmware/govmomi"
	"github.com/vmware/govmomi/find"
	"github.com/vmware/govmomi/object"
	"github.com/vmware/govmomi/property"
	"github.com/vmware/govmomi/vim25/mo"
	"github.com/vmware/govmomi/vim25/types"
)

const version = "0.1.0"

// Client wrapper for vSphere connection
type Client struct {
	client *govmomi.Client
	finder *find.Finder
}

// Connect to vSphere
func connect(ctx context.Context, server, username, password string, insecure bool) (*Client, error) {
	u, err := url.Parse(fmt.Sprintf("https://%s/sdk", server))
	if err != nil {
		return nil, fmt.Errorf("failed to parse URL: %w", err)
	}

	u.User = url.UserPassword(username, password)

	client, err := govmomi.NewClient(ctx, u, insecure)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to vSphere: %w", err)
	}

	finder := find.NewFinder(client.Client, true)

	return &Client{
		client: client,
		finder: finder,
	}, nil
}

// Datacenter represents a vSphere datacenter
type Datacenter struct {
	Name string `json:"name"`
	Path string `json:"path"`
}

// Cluster represents a vSphere cluster
type Cluster struct {
	Name string `json:"name"`
	Path string `json:"path"`
}

// Datastore represents a vSphere datastore
type Datastore struct {
	Name      string `json:"name"`
	Path      string `json:"path"`
	FreeSpace int64  `json:"freeSpace"`
	Capacity  int64  `json:"capacity"`
	Type      string `json:"type"`
}

// Network represents a vSphere network
type Network struct {
	Name string `json:"name"`
	Path string `json:"path"`
	Type string `json:"type"`
}

// List all datacenters
func (c *Client) listDatacenters(ctx context.Context) ([]Datacenter, error) {
	dcs, err := c.finder.DatacenterList(ctx, "*")
	if err != nil {
		return nil, fmt.Errorf("failed to list datacenters: %w", err)
	}

	result := make([]Datacenter, len(dcs))
	for i, dc := range dcs {
		result[i] = Datacenter{
			Name: dc.Name(),
			Path: dc.InventoryPath,
		}
	}

	return result, nil
}

// List clusters in a datacenter
func (c *Client) listClusters(ctx context.Context, datacenter string) ([]Cluster, error) {
	dc, err := c.finder.Datacenter(ctx, datacenter)
	if err != nil {
		return nil, fmt.Errorf("failed to find datacenter '%s': %w", datacenter, err)
	}

	c.finder.SetDatacenter(dc)

	clusters, err := c.finder.ClusterComputeResourceList(ctx, "*")
	if err != nil {
		return nil, fmt.Errorf("failed to list clusters: %w", err)
	}

	result := make([]Cluster, len(clusters))
	for i, cluster := range clusters {
		result[i] = Cluster{
			Name: cluster.Name(),
			Path: cluster.InventoryPath,
		}
	}

	return result, nil
}

// List datastores in a datacenter
func (c *Client) listDatastores(ctx context.Context, datacenter string) ([]Datastore, error) {
	dc, err := c.finder.Datacenter(ctx, datacenter)
	if err != nil {
		return nil, fmt.Errorf("failed to find datacenter '%s': %w", datacenter, err)
	}

	c.finder.SetDatacenter(dc)

	datastores, err := c.finder.DatastoreList(ctx, "*")
	if err != nil {
		return nil, fmt.Errorf("failed to list datastores: %w", err)
	}

	// Fetch datastore properties
	var dss []mo.Datastore
	pc := property.DefaultCollector(c.client.Client)
	refs := make([]types.ManagedObjectReference, len(datastores))
	for i, ds := range datastores {
		refs[i] = ds.Reference()
	}

	err = pc.Retrieve(ctx, refs, []string{"name", "summary"}, &dss)
	if err != nil {
		return nil, fmt.Errorf("failed to retrieve datastore properties: %w", err)
	}

	result := make([]Datastore, len(dss))
	for i, ds := range dss {
		result[i] = Datastore{
			Name:      ds.Name,
			Path:      datastores[i].InventoryPath,
			FreeSpace: ds.Summary.FreeSpace,
			Capacity:  ds.Summary.Capacity,
			Type:      ds.Summary.Type,
		}
	}

	return result, nil
}

// List networks in a datacenter
func (c *Client) listNetworks(ctx context.Context, datacenter string) ([]Network, error) {
	dc, err := c.finder.Datacenter(ctx, datacenter)
	if err != nil {
		return nil, fmt.Errorf("failed to find datacenter '%s': %w", datacenter, err)
	}

	c.finder.SetDatacenter(dc)

	networks, err := c.finder.NetworkList(ctx, "*")
	if err != nil {
		return nil, fmt.Errorf("failed to list networks: %w", err)
	}

	result := make([]Network, 0, len(networks))
	for _, net := range networks {
		var netType string
		switch net.(type) {
		case *object.Network:
			netType = "Network"
		case *object.DistributedVirtualPortgroup:
			netType = "DistributedVirtualPortgroup"
		case *object.OpaqueNetwork:
			netType = "OpaqueNetwork"
		default:
			netType = "Unknown"
		}

		result = append(result, Network{
			Name: net.GetInventoryPath(),
			Path: net.GetInventoryPath(),
			Type: netType,
		})
	}

	return result, nil
}

func main() {
	if len(os.Args) < 2 {
		printUsage()
		os.Exit(1)
	}

	command := os.Args[1]

	switch command {
	case "version", "--version", "-v":
		fmt.Printf("vsphere-helper version %s\n", version)
		os.Exit(0)
	case "help", "--help", "-h":
		printUsage()
		os.Exit(0)
	case "list-datacenters":
		listDatacentersCmd()
	case "list-clusters":
		listClustersCmd()
	case "list-datastores":
		listDatastoresCmd()
	case "list-networks":
		listNetworksCmd()
	default:
		fmt.Fprintf(os.Stderr, "Unknown command: %s\n\n", command)
		printUsage()
		os.Exit(1)
	}
}

func printUsage() {
	fmt.Println("vsphere-helper - vSphere discovery tool using govmomi")
	fmt.Println()
	fmt.Println("Usage:")
	fmt.Println("  vsphere-helper <command> [flags]")
	fmt.Println()
	fmt.Println("Commands:")
	fmt.Println("  list-datacenters          List all datacenters")
	fmt.Println("  list-clusters             List clusters in a datacenter")
	fmt.Println("  list-datastores           List datastores in a datacenter")
	fmt.Println("  list-networks             List networks in a datacenter")
	fmt.Println("  version                   Show version")
	fmt.Println("  help                      Show this help")
	fmt.Println()
	fmt.Println("Authentication:")
	fmt.Println("  All commands require vSphere connection via environment variables:")
	fmt.Println("    VSPHERE_SERVER      - vCenter server (e.g., vcenter.example.com)")
	fmt.Println("    VSPHERE_USERNAME    - vCenter username")
	fmt.Println("    VSPHERE_PASSWORD    - vCenter password")
	fmt.Println("    VSPHERE_INSECURE    - Skip SSL verification (default: false)")
	fmt.Println()
	fmt.Println("Examples:")
	fmt.Println("  # List all datacenters")
	fmt.Println("  export VSPHERE_SERVER=vcenter.example.com")
	fmt.Println("  export VSPHERE_USERNAME=administrator@vsphere.local")
	fmt.Println("  export VSPHERE_PASSWORD=password")
	fmt.Println("  vsphere-helper list-datacenters")
	fmt.Println()
	fmt.Println("  # List clusters in a datacenter")
	fmt.Println("  vsphere-helper list-clusters --datacenter DC1")
	fmt.Println()
	fmt.Println("  # List datastores with capacity info")
	fmt.Println("  vsphere-helper list-datastores --datacenter DC1")
}

func getEnvConfig() (server, username, password string, insecure bool, err error) {
	server = os.Getenv("VSPHERE_SERVER")
	username = os.Getenv("VSPHERE_USERNAME")
	password = os.Getenv("VSPHERE_PASSWORD")
	insecureStr := os.Getenv("VSPHERE_INSECURE")

	if server == "" {
		return "", "", "", false, fmt.Errorf("VSPHERE_SERVER environment variable not set")
	}
	if username == "" {
		return "", "", "", false, fmt.Errorf("VSPHERE_USERNAME environment variable not set")
	}
	if password == "" {
		return "", "", "", false, fmt.Errorf("VSPHERE_PASSWORD environment variable not set")
	}

	insecure = strings.ToLower(insecureStr) == "true" || insecureStr == "1"

	return server, username, password, insecure, nil
}

func listDatacentersCmd() {
	server, username, password, insecure, err := getEnvConfig()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	ctx := context.Background()
	client, err := connect(ctx, server, username, password, insecure)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
	defer client.client.Logout(ctx)

	dcs, err := client.listDatacenters(ctx)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	output, err := json.MarshalIndent(dcs, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error marshaling JSON: %v\n", err)
		os.Exit(1)
	}

	fmt.Println(string(output))
}

func listClustersCmd() {
	fs := flag.NewFlagSet("list-clusters", flag.ExitOnError)
	datacenter := fs.String("datacenter", "", "Datacenter name (required)")
	fs.Parse(os.Args[2:])

	if *datacenter == "" {
		fmt.Fprintf(os.Stderr, "Error: --datacenter flag is required\n")
		fs.Usage()
		os.Exit(1)
	}

	server, username, password, insecure, err := getEnvConfig()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	ctx := context.Background()
	client, err := connect(ctx, server, username, password, insecure)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
	defer client.client.Logout(ctx)

	clusters, err := client.listClusters(ctx, *datacenter)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	output, err := json.MarshalIndent(clusters, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error marshaling JSON: %v\n", err)
		os.Exit(1)
	}

	fmt.Println(string(output))
}

func listDatastoresCmd() {
	fs := flag.NewFlagSet("list-datastores", flag.ExitOnError)
	datacenter := fs.String("datacenter", "", "Datacenter name (required)")
	fs.Parse(os.Args[2:])

	if *datacenter == "" {
		fmt.Fprintf(os.Stderr, "Error: --datacenter flag is required\n")
		fs.Usage()
		os.Exit(1)
	}

	server, username, password, insecure, err := getEnvConfig()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	ctx := context.Background()
	client, err := connect(ctx, server, username, password, insecure)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
	defer client.client.Logout(ctx)

	datastores, err := client.listDatastores(ctx, *datacenter)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	output, err := json.MarshalIndent(datastores, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error marshaling JSON: %v\n", err)
		os.Exit(1)
	}

	fmt.Println(string(output))
}

func listNetworksCmd() {
	fs := flag.NewFlagSet("list-networks", flag.ExitOnError)
	datacenter := fs.String("datacenter", "", "Datacenter name (required)")
	fs.Parse(os.Args[2:])

	if *datacenter == "" {
		fmt.Fprintf(os.Stderr, "Error: --datacenter flag is required\n")
		fs.Usage()
		os.Exit(1)
	}

	server, username, password, insecure, err := getEnvConfig()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	ctx := context.Background()
	client, err := connect(ctx, server, username, password, insecure)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
	defer client.client.Logout(ctx)

	networks, err := client.listNetworks(ctx, *datacenter)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	output, err := json.MarshalIndent(networks, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error marshaling JSON: %v\n", err)
		os.Exit(1)
	}

	fmt.Println(string(output))
}
