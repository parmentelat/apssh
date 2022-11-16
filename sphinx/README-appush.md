# Remote copies with `appush` and `appull`

## Purpose

As of 0.24.x `apssh` comes with these two separate commands for automating file
copies in a parallel and asynchroneous way

## Target selections

The mechanism for selecting targets (i.e. remote ssh endpoints) is identical to
the one in `apssh`; <a href="README-apssh.html#targets-selection">refer to that section for more details</a>

## Remote file locations

You specify remote files by prefixing them with `@:` and that will be replaced by the relevant ssh endpoints

## Endpoint expansion

In all file parameters, it is possible to use the following specials that get expanded with the actual ssh endpoint information

* `{host}`: the short hostname
* `{fqdn}`: the long hostname
* `{user}`: the username

## Examples

### Pushing

Copy the same local file over to a variety of hosts

- copy one local file on all remote home dirs

```
appush -t the_targets local_file @:
```
- likewise but with several local files, and store remote copies in /etc/

```
appush -t the_targets local_file1 local_file2 @:/etc
```

- in this third example here we would copy
  - `local-box1` onto `box1.inria.fr:/etc/some-file`
  - `local-box2` into `box2:/etc/some-file`

```
appush -t box1.inria.fr,box2 local-{host} @:/etc/some-file
```


### Pulling

The same logic is at work for the other way around

- copy the `/etc/fedora-release` files of 2 boxes, into respectively
  - `subdir/box1-fedora-release`
  - `subdir/box2-fedora-release`

```
appull -t box1.inria.fr,box2 @:/etc/fedora-release the-releases/{host}-fedora-release
```

- same but fetch several files in one go; this will create locally
  - `the-releases/box1/fedora-release` and  `the-releases/box1/lsb-release` for the first box
  - same 2 files in the `the-releases/box2/` for the second box

```
appull -t -t box1.inria.fr,box2 @:/etc/fedora-release @:/etc/lsb-release the-releases/{host}/
```
