# A Decentralized and Self-Adaptive Approach for Monitoring Volatile Edge Environments

## Abstract
Edge computing offers resources for latency-sensitive Internet of Things (IoT) workloads through highly distributed computing
infrastructure at the network edge. Monitoring systems are essential for efficiently managing resources and application workloads by
collecting, storing, and providing relevant information about the state of the resources. However, traditional monitoring systems have a
centralized architecture for both data plane and control plane, which collects and stores the data in centralized remote servers. Such an
architecture increases the communication latency for information storage and retrieval. Also, it creates a failure bottleneck, especially
in Edge, where infrastructures are often built upon failure-prone, unsophisticated computing and network resources. Moreover, the
Edge resources are arbitrarily (de)provisioned, which creates further challenges for providing quick and trustworthy data. Thus, it is
crucial to design and build a monitoring system that is decentralized, fast, and trustworthy for such volatile Edge computing systems.
Therefore, we propose the Decentralised Edge Monitoring (DEMon) framework, a decentralized, self-adaptive monitoring system for
highly volatile Edge environments. DEMon leverages the stochastic Gossip communication protocol at its core. It develops techniques
and a framework for efficient control of information dissemination, communication, and retrieval, avoiding a single point of failure
and ensuring fast and trustworthy data access. Its decentralized control enables self-adaptive management of monitoring parameters,
addressing the tradeoffs between the Quality of Service of monitoring and resource consumption. We implement the proposed system
as a lightweight and portable container-based monitoring system and evaluate it through empirical experiments. We also present an
experimental use case demonstrating the feasibility of the proposed system. The results show that DEMon efficiently disseminates and
retrieves the monitoring information, addressing the above-mentioned challenges.

## Baseline Comparison with [FogMon2](https://github.com/di-unipi-socc/FogMon/tree/liscio-2.0)
We compare DEMon with a structured monitoring system [FogMon2](https://github.com/di-unipi-socc/FogMon/tree/liscio-2.0). In order to compare the metrics measured in the experiments with DEMon, 
we implemented minor changes in [FogMon2](FogMon2). The changes are as follows:
### Addional Table in the Database
We added a new Table in the database to store additional information about the communication between the nodes. Following adjustment were
made in the code: 
- In the [leader](FogMon2/src/leader/leader_storage.cpp#L27) and [follower](FogMon2/src/follower/storage.cpp#L82) storage a new table "Test" is introduced, which should store an entry for each communication from a node to a node.
- The table has the following columns: 
    - id: auto-incremented integer
    - sender: the id of the sender node
    - receiver: the id of the receiver node
    - timestamp: the timestamp of the communication
    - isLeader: a boolean value to indicate if the sender is a leader or not
- After a leader [gossips](FogMon2/src/leader/leader.cpp#L182-188) to another leader the added method [addGossipMsg](FogMon2/src/leader/leader_storage.cpp#L37-43) is called to store the communication in the database.
- After a follower [pushed](FogMon2/src/follower/follower.cpp#L565) a new report to its leader the added method [addFollowerMsgToLeader](FogMon2/src/follower/storage.cpp#L91-97) is called to store the communication in the database.
- Those 2 methods were also mentioned in the respective header files and interfaces.

### Minor change to improve CPU usage via Docker
- We introduced a waiting [time](FogMon2/src/main/main.cpp#L199) as described in this [Issue](https://github.com/di-unipi-socc/FogMon/issues/15) to reduce the CPU usage of the FogMon2 system using Docker Container.

### Approach
In order to preserve the structure of FogMon2 we organised our experiments as follows:
- At first the minimum number(10) of nodes is run via docker with a single leader.
- Depending on the leader formula we implemented a waiting time in order to let the system stabilize, select new leaders and converge.
- After set time the databases of the nodes are copied to the host machine for further analysis.
- The databases are then merged into a single database ordered by timestamp.
- By the isLeader column we can identify the (new) leaders in the system.
- Now the whole process starts again with increasing system sizes (20-80) with a minor change in order to not overload a single leader: newly added nodes(=follower at the beginning) are now evenly distributed to the already selected leaders.