#[derive(Debug)]
pub struct VotingRowData {
    pub create_voting: Option<serde_json::Value>,
    pub storage_ballot: Option<serde_json::Value>,
    pub register_voters: Option<serde_json::Value>,
    pub issue_ballot: Option<serde_json::Value>,
    pub storage_private_key: Option<serde_json::Value>,
    pub storage_history: Option<serde_json::Value>,
    pub storage_decode_ballot: Option<serde_json::Value>,
    pub storage_result: Option<serde_json::Value>,
    pub storage_observe: Option<serde_json::Value>,
    pub storage_ballot_config: Option<serde_json::Value>,
    pub hash: String,
    pub tx_type: Option<String>,
    pub timestamp: Option<i64>,
    pub sid: Option<String>,
    pub io: Option<String>,
    pub voting_id: Option<String>,
}

#[derive(Debug, Hash, PartialEq, Eq)]
pub struct HashedTxRow {
    pub tx_hash: String,
    pub row_hash: String,
}

pub trait VotingRow: Sync + Send {
    fn to_data(&self) -> VotingRowData;
    fn compute_hash(&self) -> HashedTxRow;
}
