# docs

when first installing, you need to get the password to create the user

```shell
kubectl get secret postgres-v15-superuser -o jsonpath='{.data.password}' -n databases | base64 --decode && echo
```

and then you connect with pgcli like this:

```shell
pgcli postgresql://postgres:asdibasidbasdiuasbdiuasd@192.168.100.102:5432/postgres
```

commands to create a user with the good stuff:

```sql
CREATE DATABASE david;
CREATE USER david WITH PASSWORD 'pizza';
ALTER USER david WITH SUPERUSER;
```

and then you're done
