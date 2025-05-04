<div align="center">

### <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f680/512.gif" alt="🚀" width="16" height="16"> My Home Repository <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f6a7/512.gif" alt="🚧" width="16" height="16">

_... managed with Flux, Renovate, and GitHub Actions_ <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f916/512.gif" alt="🤖" width="16" height="16">

</div>

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f4a1/512.gif" alt="💡" width="20" height="20"> Overview

This is a repository for my home infrastructure and Kubernetes cluster. It contains all my confuration files for my personal, home cluster that is separate to my production cluster.

---

You can look through my folders and set things up for yourself, but one of the best things you can do is visit my [website](https://davidilie.com) or follow me on [X](https://x.com/MrDavidIlie)

## 🚀 Information

This is running as a virtual machine on my Proxmox server called Nucleus, that contains three virtual machines

| Name        | Information           | Resources                                   |
| ----------- | --------------------- | ------------------------------------------- |
| truenas     | My NAS software       | 16 cores, 128GB RAM, 4x 4TB HDD, NVME cache |
| kubernetes  | All my home workloads | 8 cores, 64GB RAM, RTX 2080 passed through  |
| pterodactyl | Game servers          | 4 cores, 32GB RAM                           |

## 🧠 My server, Nucleus

I own a Dell R730, which is an absolute powerhouse. To house my HDDs, I have an old HP server where I just use its backplane and connect a very long SASS cable to my R730 for TrueNAS

<img src="https://github.com/user-attachments/assets/640a0c91-5a9e-43aa-948f-afa1265cab28" alt="My Server">

<img src="https://github.com/user-attachments/assets/59d3a4c7-2d90-41ec-b672-e81999f86938" alt="My Proxmox Stats">

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f64f/512.gif" alt="🙏" width="20" height="20"> Gratitude and Thanks

Thanks to all the people who donate their time to the [Home Operations](https://discord.gg/home-operations) Discord community. Be sure to check out [kubesearch.dev](https://kubesearch.dev/) for ideas on how to deploy applications or get ideas on what you could deploy.
