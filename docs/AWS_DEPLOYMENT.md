# Docker and AWS deployment

## Run locally

Install/start Docker Desktop in Linux-container mode (or Docker Engine with the Compose plugin on Linux). Keep your configured `.env` in the repository root. From that root:

```powershell
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose logs -f backend
```

Open http://127.0.0.1:8080. The frontend serves the production build and forwards `/api/*` to the backend. Port 8000 is internal to the Docker network. Existing Vite/API processes on 5173/8000 do not conflict with this setup.

The container uses a fresh Linux index, not the Windows `.data` directory. Select each bid in the UI and click **Update bid index** before searching. First indexing downloads the embedding model and can take longer; reranking downloads its model on first use. Allow outbound HTTPS to the model registry and configured Gemini endpoint. Extraction automatically indexes its selected folder. In the folder dialog use `/bids/Bid1` or `/bids/Bid2`, not a Windows path.

The two supplied bid folders are read-only bind mounts. Add another folder by adding a mount such as `./MyBid:/bids/MyBid:ro` under the backend service and recreating it with `docker compose up -d`. Source documents and credentials are excluded from image build contexts. The backend runs as UID 10001; mounted documents must be readable by that user.

```powershell
docker compose down
docker compose up -d --build
```

`down` keeps named volumes; **do not use `down -v`** unless you intend to delete indexes, cached models, saved outputs and traces. The volumes are `rfp_data` and `rfp_outputs`, prefixed by the Compose project name. Download generated records using the UI's Export JSON button.

## Host on AWS EC2

1. Launch an x86_64 Ubuntu EC2 instance with an EBS volume. Start with 2 vCPUs, 8 GiB RAM and 30 GiB disk as a trial capacity estimate; measure memory/disk use during indexing and extraction before choosing final capacity. Models run on CPU; a GPU is not required. Use an IAM instance role rather than placing AWS access keys in the repository.
2. Install Docker Engine and the Compose plugin using the [official Ubuntu installation instructions](https://docs.docker.com/engine/install/ubuntu/). Verify `docker --version` and `docker compose version`. Enable Docker at boot with `sudo systemctl enable --now docker`.
3. Clone/copy this repository to the instance, including Bid1/Bid2 source folders. Create `.env` on the host with your Gemini settings (do not commit it); restrict it with `chmod 600 .env`. The image never includes `.env`. Use `sudo docker compose` if your user is not permitted to access Docker.
4. For a private demo, keep the default localhost binding. Connect through SSH:

   ```bash
   ssh -L 8080:127.0.0.1:8080 ubuntu@YOUR_EC2_ADDRESS
   ```

   Then open http://127.0.0.1:8080 on your computer. Allow SSH only from your IP in the instance security group.

5. For a domain behind an Application Load Balancer, set `RFP_BIND_ADDRESS=0.0.0.0` and `RFP_HTTP_PORT=8080` in `.env`, then run `sudo docker compose up -d --build`. Use an HTTPS listener with an ACM certificate; forward to instance port 8080. Set target health checking to `/healthz` and the load balancer idle timeout to 1800 seconds to accommodate extraction. Restrict the instance's inbound 8080 rule to the load balancer security group; never open backend port 8000. See [AWS security-group guidance](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/security-group-rules-reference.html).
6. This application has no built-in login. Before granting internet access, protect the load balancer with authentication (for example ALB OIDC/Cognito) or keep access restricted to a trusted network. Otherwise anyone with access could trigger indexing and billable LLM calls. HTTP between ALB and the host stays inside the VPC; the browser connects over HTTPS.
7. Index each bid in the UI, run a search, ask a cited question, and review extraction fields. `docker compose ps` checks process readiness; a passing health check does not verify model credentials or generated facts.

Keep the Docker volumes on EBS-backed storage. Set an appropriate EBS retention policy and take backups/snapshots; stop the backend during volume backups to keep SQLite/Qdrant state consistent. A named Docker volume survives container replacement, but is not automatically durable after its EC2 disk is deleted. See [AWS EBS storage guidance](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/storage_ebs.html).

Update with `git pull` and `sudo docker compose up -d --build`. Run one backend container and one Uvicorn worker. Do not scale this deployment across hosts or share these volume directories between active replicas. ECS/Fargate multi-replica deployment requires moving embedded Qdrant to a server and redesigning manifest/output persistence first.

## Decisions and verification

- Two containers separate static serving from model/API dependencies; Nginx gives same-origin API access and SPA fallback without a production Vite server.
- Python 3.12 matches the validated interpreter; a Linux dependency file removes Windows-only `pywin32` and test packages. PyTorch uses CPU wheels to avoid unnecessary CUDA image size. Dependency pins originate from the existing verified lock; Linux wheel availability still requires an actual build.
- Only project code enters images; keys, documents, traces and model caches are mounted/configured at runtime for smaller images and to avoid embedding private data.
- Bind localhost by default so deployment does not expose unauthenticated generation before the operator configures network/authentication access.
- Explicit volumes preserve costly indexes/models and generated records across container updates.
- The CLI's `--host` option retains localhost as the normal default and permits container-network binding only when explicitly configured.

Compose configuration validation and the Python test suite pass. Full image builds, Nginx runtime proxy checks and AWS deployment are unverified here because the local Docker engine is not running. Run `docker compose up -d --build` on a working engine and complete the smoke steps above before treating the deployment as verified.
