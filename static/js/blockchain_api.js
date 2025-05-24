/**
 * Blockchain API Client Library
 * 
 * A client library for interacting with the cryptocurrency transaction API
 */
class BlockchainApi {
    /**
     * Initialize the API client
     * 
     * @param {string} baseUrl - Base URL for the API (default: current host)
     */
    constructor(baseUrl = null) {
        this.baseUrl = baseUrl || window.location.origin;
        this.apiPath = '/api';
        this._blockchains = null;
    }

    /**
     * Prepare a transaction for a specific blockchain
     * 
     * @param {string} blockchain - Blockchain name (e.g., 'ethereum', 'bitcoin', 'bsc')
     * @param {object} params - Transaction parameters
     * @param {string} params.sender_address - Sender's address
     * @param {string} params.recipient_address - Recipient's address
     * @param {string} params.amount - Amount to send
     * @param {string} [params.smart_contract_address] - Smart contract address (for token transfers)
     * @returns {Promise<object>} - Transaction preparation result
     */
    async prepareTransaction(blockchain, params) {
        // Validate inputs
        if (!blockchain) throw new Error('Blockchain name is required');
        if (!params.sender_address) throw new Error('Sender address is required');
        if (!params.recipient_address) throw new Error('Recipient address is required');
        if (!params.amount) throw new Error('Amount is required');

        // Normalize blockchain name to lowercase
        blockchain = blockchain.toLowerCase();

        // Make API request
        try {
            const response = await fetch(`${this.baseUrl}${this.apiPath}/${blockchain}/prepare`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(params),
                credentials: 'include'
            });

            // Parse response
            const result = await response.json();

            // Check for errors
            if (!response.ok) {
                throw new Error(result.message || `Error preparing ${blockchain} transaction`);
            }

            return result;
        } catch (error) {
            console.error(`Error preparing ${blockchain} transaction:`, error);
            throw error;
        }
    }

    /**
     * Confirm and send a prepared transaction
     * 
     * @param {string} blockchain - Blockchain name
     * @param {object} params - Confirmation parameters
     * @param {string} params.transaction_id - ID of the prepared transaction
     * @param {string} params.private_key - Private key to sign the transaction
     * @returns {Promise<object>} - Transaction confirmation result
     */
    async confirmTransaction(blockchain, params) {
        // Validate inputs
        if (!blockchain) throw new Error('Blockchain name is required');
        if (!params.transaction_id) throw new Error('Transaction ID is required');
        if (!params.private_key) throw new Error('Private key is required');

        // Normalize blockchain name to lowercase
        blockchain = blockchain.toLowerCase();

        // Make API request
        try {
            const response = await fetch(`${this.baseUrl}${this.apiPath}/${blockchain}/confirm`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(params),
                credentials: 'include'
            });

            // Parse response
            const result = await response.json();

            // Check for errors
            if (!response.ok) {
                throw new Error(result.message || `Error confirming ${blockchain} transaction`);
            }

            return result;
        } catch (error) {
            console.error(`Error confirming ${blockchain} transaction:`, error);
            throw error;
        }
    }

    /**
     * Get list of supported blockchains
     * 
     * @returns {Promise<string[]>} - List of supported blockchain names
     */
    async getSupportedBlockchains() {
        try {
            const response = await fetch(`${this.baseUrl}${this.apiPath}/test`, {
                method: 'GET',
                credentials: 'include'
            });

            // Parse response
            const result = await response.json();

            // Check for errors
            if (!response.ok) {
                throw new Error(result.message || 'Error getting supported blockchains');
            }

            return result.available_blockchains || [];
        } catch (error) {
            console.error('Error getting supported blockchains:', error);
            throw error;
        }
    }
    
    /**
     * Get detailed blockchain information
     * 
     * @returns {Promise<object[]>} - Array of blockchain configuration objects
     */
    async getBlockchainDetails() {
        // Use cached value if available
        if (this._blockchains) {
            return this._blockchains;
        }
        
        try {
            const response = await fetch(`${this.baseUrl}${this.apiPath}/blockchains`, {
                method: 'GET',
                credentials: 'include'
            });

            // Parse response
            const result = await response.json();

            // Check for errors
            if (!response.ok) {
                throw new Error(result.message || 'Error getting blockchain details');
            }

            // Cache the result
            this._blockchains = result.blockchains || [];
            return this._blockchains;
        } catch (error) {
            console.error('Error getting blockchain details:', error);
            throw error;
        }
    }
    
    /**
     * Get blockchain information for a specific blockchain
     * 
     * @param {string} blockchain - Blockchain name
     * @returns {Promise<object>} - Blockchain configuration object
     */
    async getBlockchainInfo(blockchain) {
        // Normalize blockchain name to lowercase
        const normalizedName = blockchain.toLowerCase();
        
        // Get all blockchain details
        const blockchains = await this.getBlockchainDetails();
        
        // Find the requested blockchain
        const found = blockchains.find(b => 
            b.name.toLowerCase() === normalizedName || 
            (b.name_variants && b.name_variants.some(v => v.toLowerCase() === normalizedName))
        );
        
        if (!found) {
            throw new Error(`Blockchain '${blockchain}' not found`);
        }
        
        return found;
    }
    
    /**
     * Get explorer URL for a transaction
     * 
     * @param {string} blockchain - Blockchain name
     * @param {string} txHash - Transaction hash
     * @returns {Promise<string>} - Explorer URL
     */
    async getExplorerUrl(blockchain, txHash) {
        // Get blockchain info
        const info = await this.getBlockchainInfo(blockchain);
        
        if (!info.explorer_url) {
            throw new Error(`No explorer URL defined for ${blockchain}`);
        }
        
        // Generate explorer URL
        return `${info.explorer_url}/tx/${txHash}`;
    }
}

// Export the API class
if (typeof module !== 'undefined' && module.exports) {
    module.exports = BlockchainApi;
} else if (typeof window !== 'undefined') {
    // Make available in browser
    window.BlockchainApi = BlockchainApi;
} 