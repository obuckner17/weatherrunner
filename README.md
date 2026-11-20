[README.md](https://github.com/user-attachments/files/35187510/README.md)
# Getting started with Akamai Cloud

Run an app on Akamai Cloud in one hour. Use the labs below during build time.

Friday, November 20, 2026. Time and place are on the [event page](https://luma.com/akamai-build-nov20).

## Start here

1. [Create an account with $300 in credit](https://login.linode.com/signup?promo=akm-eve-git-bell-300-103126-W204). A payment method is required.
2. Follow [WORKSHOP.md](WORKSHOP.md). Setup and the whole hour are on that page.

You will leave with an app running on a Linode, a Linux server, and know how to update it and read its logs.

## Building your project

Open the lab you need.

| I need to | Open this | Time |
|---|---|---|
| Call a model | [Inference](01-inference/README.md) | 10 min |
| Run an app on a server | [Linode](02-linode/README.md) | Allow 25 min |
| Save data or search text by meaning | [PostgreSQL](03-database/README.md) | 10 min, plus 8 waiting |
| Store files | [Object Storage](04-object-storage/README.md) | 10 min |
| Use Kubernetes | [LKE](05-lke/README.md) | 15 min, plus 3 waiting |
| Choose another service | [Service guide](docs/services.md) | 2 min |

Use the [workshop app](demo/README.md) as your starting point. LKE is optional for teams that already use Kubernetes. The labs use Cloud Manager, Akamai's web console, with optional [CLI instructions](00-setup/cli.md).

## Judging

40% other services, 20% inference, 20% usefulness, 20% creativity. More services do not automatically mean a higher score. Teams have up to 3 people. Solo projects are welcome. See [judging and submission](docs/judging.md).

## Help and cleanup

- Ask a helper or read [troubleshooting](docs/troubleshooting.md).
- When you finish building, follow the [cleanup steps](docs/cleanup.md) to stop billing.
