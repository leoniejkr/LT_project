import type { Actions } from '@sveltejs/kit';


export const actions = {
    default : async ( event ) => {
        // TODO implement file upload of picture and metadata
        event;
    }
} satisfies Actions;

export const prerender = false;