# svtplay-dl

container version of the script.

# usage
```sh
docker run -it --rm  -u $(id -u):$(id -g)  -v "$(pwd):/data" spaam/svtplay-dl <args>
```
or create an alias:
##### bash (~/.bashrc)
```
alias svtplay-dl='docker run -it --rm  -u $(id -u):$(id -g)  -v "$(pwd):/data" spaam/svtplay-dl'
```
##### zsh (~/.zshrc)
```
alias svtplay-dl='docker run -it --rm  -u $(id -u):$(id -g)  -v "$(pwd):/data" spaam/svtplay-dl'
```

# build example
```sh
docker build -t svtplay-dl .
```
